#!/usr/bin/env python3
"""Build local screen previews. Google Drive is read-only and never a runtime dependency.
Default: report only. --apply writes hashed assets/catalog; nothing is pushed/deployed.
"""
import argparse
import concurrent.futures
import copy
import hashlib
import gzip
import zlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageOps, __version__ as PILLOW_VERSION, features

ROOT = Path(__file__).resolve().parents[1]
EDGES = (600, 1600)
GENERATOR = {"version": 1, "edges": list(EDGES), "format": "WebP", "lossless": True,
             "method": 4, "exact": True, "resampling": "RGB/RGBA before LANCZOS",
             "pillow": PILLOW_VERSION, "libwebp": features.version("webp")}
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("Invalid Drive file/folder ID")
    return value


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(default)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".motif-", suffix=".tmp", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(data)
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def http_get(url, headers=None, maximum=64 * 1024 * 1024):
    """GET only; errors never disclose URLs, tokens or API keys."""
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers=headers or {}, method="GET")
            with urllib.request.urlopen(request, timeout=40) as response:
                body = response.read(maximum + 1)
                content_type = response.headers.get("Content-Type", "")
                encoding = response.headers.get("Content-Encoding", "").lower()
            if encoding == "gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                    body = compressed.read(maximum + 1)
            elif encoding == "deflate":
                decoder = zlib.decompressobj()
                body = decoder.decompress(body, maximum + 1)
            if len(body) > maximum:
                raise ValueError("Response exceeds import limit")
            return body, content_type
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
            code = getattr(error, "code", None)
            if attempt == 4 or code in (400, 401, 403, 404):
                raise RuntimeError("Read-only source request failed" + (f" (HTTP {code})" if code else "")) from None
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError("Source request failed")


class DriveReader:
    def __init__(self, key=None, token=None):
        self.key = key or os.environ.get("GOOGLE_DRIVE_API_KEY")
        self.token = token or os.environ.get("GOOGLE_DRIVE_ACCESS_TOKEN")
        if not self.key and not self.token:
            raise ValueError("Folder discovery requires GOOGLE_DRIVE_API_KEY (public sources) or GOOGLE_DRIVE_ACCESS_TOKEN (read-only access). Never put these in the app or repository.")

    def list_children(self, folder_id):
        valid_id(folder_id)
        page = None
        while True:
            params = {"q": f"'{folder_id}' in parents and trashed = false", "pageSize": 1000,
                      "orderBy": "name", "spaces": "drive", "supportsAllDrives": "true",
                      "includeItemsFromAllDrives": "true",
                      "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,md5Checksum,size,version,webViewLink)"}
            if self.key:
                params["key"] = self.key
            if page:
                params["pageToken"] = page
            headers = {"Accept": "application/json"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            body, _ = http_get("https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(params), headers, 16 * 1024 * 1024)
            data = json.loads(body)
            yield from data.get("files", [])
            page = data.get("nextPageToken")
            if not page:
                break


def discover_sources(config, reader):
    if config.get("version") != 1 or config.get("deleteMissing") is not False:
        raise ValueError("Unsupported source configuration; automatic deletion is prohibited")
    discovered = {}
    for root in config["roots"]:
        root_id = valid_id(root["folderId"])
        seen = set()
        stack = [(root_id, [], [])]
        while stack:
            folder_id, names, ids = stack.pop()
            if folder_id in seen:
                continue
            seen.add(folder_id)
            children = sorted(reader.list_children(folder_id), key=lambda item: (item["name"], item["id"]))
            for item in children:
                item_id = valid_id(item["id"])
                name = item["name"]
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    excluded = any(part.casefold() in name.casefold() for part in root.get("excludeFolderNamesContaining", []))
                    if not excluded and (not names or root.get("recursive", True)):
                        stack.append((item_id, names + [name], ids + [item_id]))
                    continue
                if item["mimeType"] not in config["imageMimeTypes"]:
                    continue
                if not names and not root.get("includeRootImages", False):
                    continue
                category = root.get("category") or (names[0] if names else root.get("label", "Weitere Motive"))
                source = {"provider": "google-drive", "fileId": item_id,
                          "originalUrl": f"https://drive.google.com/file/d/{item_id}/view",
                          "rootFolderId": root_id, "folderIds": ids, "folderNames": names,
                          "originalFilename": name, "mimeType": item["mimeType"],
                          "modifiedTime": item.get("modifiedTime"), "md5Checksum": item.get("md5Checksum"),
                          "size": item.get("size"), "version": item.get("version")}
                record = {"id": item_id, "name": re.sub(r"\.[^/.]+$", "", name), "category": category, "source": source}
                if item_id in discovered and discovered[item_id]["category"] != category:
                    raise ValueError("A Drive image occurs in conflicting categories: " + item_id)
                discovered[item_id] = record
    return list(discovered.values())


def source_fingerprint(source):
    fields = {key: source.get(key) for key in ("md5Checksum", "modifiedTime", "size", "version")}
    return digest(json.dumps(fields, sort_keys=True).encode()) if any(fields.values()) else None


def source_for_id(file_id):
    valid_id(file_id)
    return {"provider": "google-drive", "fileId": file_id,
            "originalUrl": f"https://drive.google.com/file/d/{file_id}/view",
            "originalFilename": None, "rootFolderId": None,
            "modifiedTime": None, "md5Checksum": None, "size": None, "version": None}


def preview_source(file_id, cache, fingerprint=None, refresh=False):
    valid_id(file_id)
    image_path = cache / (file_id + ".preview")
    info_path = cache / (file_id + ".json")
    info = read_json(info_path, {})
    if not refresh and image_path.exists() and info.get("fingerprint") == fingerprint:
        blob = image_path.read_bytes()
        if digest(blob) == info.get("sha256"):
            return blob, info["mimeType"]
    params = {"id": file_id, "sz": "w1600"}
    if fingerprint:
        params["v"] = fingerprint
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate"}
    suffix = "?v=" + fingerprint if fingerprint else ""
    candidates = ["https://drive.google.com/thumbnail?" + urllib.parse.urlencode(params),
                  f"https://lh3.googleusercontent.com/d/{file_id}=w1600" + suffix,
                  f"https://lh3.googleusercontent.com/d/{file_id}=s1600" + suffix,
                  "https://drive.google.com/thumbnail?" + urllib.parse.urlencode({"sz": "w1600", "id": file_id, **({"v": fingerprint} if fingerprint else {})})]
    last_error = None
    for candidate in candidates:
        try:
            blob, content_type = http_get(candidate, headers)
            # Never cache a login document or error page as an image.
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
            break
        except (RuntimeError, OSError, ValueError) as error:
            last_error = error
    else:
        raise RuntimeError("No valid public screen preview available: " + str(last_error)) from None
    atomic_write(image_path, blob)
    atomic_write(info_path, json_bytes({"sha256": digest(blob), "mimeType": content_type, "fingerprint": fingerprint}))
    return blob, content_type


def open_source(blob):
    with Image.open(io.BytesIO(blob)) as image:
        image.load()
        fmt = image.format
        oriented = ImageOps.exif_transpose(image)
        alpha = oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info
        # Convert bilevel/palette images BEFORE resizing so fine lines receive LANCZOS antialiasing.
        normalized = oriented.convert("RGBA" if alpha else "RGB")
        icc = oriented.info.get("icc_profile")
    return normalized, fmt, icc


def make_variant(source, edge, icc=None):
    image = source.copy()
    image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    options = {"icc_profile": icc} if icc else {}
    image.save(encoded, format="WEBP", lossless=True, method=4, exact=True, **options)
    payload = encoded.getvalue()
    pixels = image.convert("RGBA").tobytes()
    with Image.open(io.BytesIO(payload)) as decoded:
        if decoded.convert("RGBA").tobytes() != pixels:
            raise ValueError("Lossless round-trip check failed")
    return payload, {"width": image.width, "height": image.height, "bytes": len(payload),
                     "sha256": digest(payload), "pixelSha256": digest(pixels), "losslessVerified": True}


def asset_path(root, path):
    if not isinstance(path, str) or not path.startswith("assets/motifs/"):
        raise ValueError("Asset path must be local to assets/motifs")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to((root / "assets/motifs").resolve()):
        raise ValueError("Asset escapes output directory")
    return resolved


def valid_variants(root, entry):
    try:
        for edge in EDGES:
            meta = entry["variants"][str(edge)]
            payload = asset_path(root, meta["path"]).read_bytes()
            if len(payload) != meta["bytes"] or digest(payload) != meta["sha256"]:
                return False
        return True
    except (OSError, KeyError, TypeError, ValueError):
        return False


def import_record(record, old, root, cache, refresh=False, compatible=False):
    file_id = valid_id(record["id"])
    source = record["source"]
    fingerprint = source_fingerprint(source)
    if old and compatible and not refresh and old.get("sourceFingerprint") == fingerprint and valid_variants(root, old):
        entry = copy.deepcopy(old)
        entry.update({"name": record["name"], "category": record["category"], "source": source})
        return entry, "unchanged"
    blob, mime = preview_source(file_id, cache, fingerprint, refresh)
    preview_hash = digest(blob)
    if old and compatible and old.get("previewSource", {}).get("sha256") == preview_hash and valid_variants(root, old):
        entry = copy.deepcopy(old)
        entry.update({"name": record["name"], "category": record["category"], "source": source, "sourceFingerprint": fingerprint})
        return entry, "metadata-only"
    image, fmt, icc = open_source(blob)
    variants = {}
    for edge in EDGES:
        payload, meta = make_variant(image, edge, icc)
        path = f"assets/motifs/{file_id}/{edge}-{meta['sha256'][:16]}.webp"
        destination = asset_path(root, path)
        if destination.exists() and digest(destination.read_bytes()) != meta["sha256"]:
            raise ValueError("Asset name collision")
        if not destination.exists():
            atomic_write(destination, payload)
        variants[str(edge)] = {"path": path, **meta}
    entry = {"id": file_id, "name": record["name"], "category": record["category"],
             "source": source, "sourceFingerprint": fingerprint,
             "previewSource": {"kind": "Drive screen thumbnail, not a laser production file", "requestedSize": "w1600; s1600 import fallback",
                               "sha256": preview_hash, "bytes": len(blob), "mimeType": mime,
                               "format": fmt, "width": image.width, "height": image.height},
             "variants": variants}
    return entry, "generated"


def build_catalog(entries):
    result = []
    for entry in entries:
        images = [{"url": "./" + entry["variants"][str(edge)]["path"], "edge": edge,
                   "width": entry["variants"][str(edge)]["width"], "height": entry["variants"][str(edge)]["height"]} for edge in EDGES]
        result.append({"id": entry["id"], "name": entry["name"], "category": entry["category"],
                       "url": images[0]["url"], "detailUrl": images[1]["url"], "images": images})
    return result


def commit_metadata(root, catalog, manifest):
    """Only after all images succeed. Roll back both metadata files on a write failure."""
    paths = [root / "catalog.json", root / "data/motifs-manifest.json"]
    old = [p.read_bytes() if p.exists() else None for p in paths]
    try:
        atomic_write(paths[0], json_bytes(catalog))
        atomic_write(paths[1], json_bytes(manifest))
    except Exception:
        for path, previous in zip(paths, old):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, previous)
        raise


def validate(root, cache=None):
    manifest = read_json(root / "data/motifs-manifest.json")
    catalog = read_json(root / "catalog.json")
    entries = manifest["motifs"]
    if len({d["id"] for d in entries}) != len(entries) or build_catalog(entries) != catalog:
        raise ValueError("Catalog/manifest mismatch or duplicate IDs")
    baseline = read_json(root / "data/motifs-baseline.json")["motifs"]
    ids = {d["id"] for d in entries}
    if not {d["id"] for d in baseline}.issubset(ids):
        raise ValueError("An original motif ID was removed")
    files, total, compared = 0, 0, 0
    for entry in entries:
        if entry["source"]["fileId"] != entry["id"] or entry["source"]["originalUrl"] != f"https://drive.google.com/file/d/{entry['id']}/view":
            raise ValueError("Original file mapping mismatch")
        source = None
        if cache is not None:
            payload = (cache / (entry["id"] + ".preview")).read_bytes()
            if digest(payload) != entry["previewSource"]["sha256"]:
                raise ValueError("Source cache checksum mismatch")
            source, _, _ = open_source(payload)
        for edge in EDGES:
            meta = entry["variants"][str(edge)]
            payload = asset_path(root, meta["path"]).read_bytes()
            if digest(payload) != meta["sha256"] or len(payload) != meta["bytes"]:
                raise ValueError("Asset checksum/size mismatch: " + entry["id"])
            with Image.open(io.BytesIO(payload)) as decoded:
                decoded.load()
                if decoded.format != "WEBP" or decoded.size != (meta["width"], meta["height"]) or max(decoded.size) > edge:
                    raise ValueError("Invalid preview dimensions/format")
                pixels = decoded.convert("RGBA").tobytes()
            if digest(pixels) != meta["pixelSha256"]:
                raise ValueError("Decoded pixels differ from verified manifest")
            if source is not None:
                reference = source.copy()
                reference.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                if reference.size != (meta["width"], meta["height"]) or reference.convert("RGBA").tobytes() != pixels:
                    raise ValueError("Preview quality/alpha differs from source scaling")
                compared += 1
            if meta["width"] > entry["previewSource"]["width"] or meta["height"] > entry["previewSource"]["height"]:
                raise ValueError("Upscaling detected")
            files += 1
            total += len(payload)
    return {"motifs": len(entries), "files": files, "bytes": total, "sourcePixelComparisons": compared,
            "baselineIdsPreserved": len(baseline)}


def run(args):
    root = args.repo.resolve()
    if args.validate:
        print(json.dumps(validate(root, args.verify_source_cache), ensure_ascii=False))
        return 0
    catalog = read_json(root / "catalog.json")
    old_manifest = read_json(root / "data/motifs-manifest.json", {})
    old_entries = {entry["id"]: entry for entry in old_manifest.get("motifs", [])}
    records = {entry["id"]: {"id": entry["id"], "name": entry["name"], "category": entry["category"],
                             "source": copy.deepcopy(old_entries.get(entry["id"], {}).get("source") or source_for_id(entry["id"]))} for entry in catalog}
    discovered_ids = None
    if args.discover:
        discovered = discover_sources(read_json(root / args.config), DriveReader())
        discovered_ids = {item["id"] for item in discovered}
        for entry in discovered:
            records[entry["id"]] = entry
    compatible = old_manifest.get("generator") == GENERATOR
    report = {"mode": "apply" if args.apply else "dry-run", "catalogCount": len(catalog), "plannedCount": len(records),
              "newIds": sorted(set(records) - set(old_entries)),
              "missingFromDiscoveryRetained": sorted(set(old_entries) - discovered_ids) if discovered_ids is not None else [],
              "driveAccess": "GET only; originals are never modified", "publishes": False}
    if not args.apply:
        report["needsImport"] = [record["id"] for record in records.values() if args.refresh or not compatible or record["id"] not in old_entries or source_fingerprint(record["source"]) != old_entries[record["id"]].get("sourceFingerprint") or not valid_variants(root, old_entries[record["id"]])]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    cache = args.cache.resolve()
    if cache.is_relative_to(root):
        raise ValueError("Source cache must be outside the repository; production/source files must not be committed")
    outcomes, errors, counters = {}, [], {}
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(import_record, record, old_entries.get(record["id"]), root, cache, args.refresh, compatible): record["id"] for record in records.values()}
        for future in concurrent.futures.as_completed(futures):
            file_id = futures[future]
            try:
                entry, action = future.result()
                outcomes[file_id] = entry
                counters[action] = counters.get(action, 0) + 1
            except Exception as error:
                # Exception text from network functions is deliberately credential-free.
                errors.append({"id": file_id, "error": type(error).__name__ + ": " + str(error)})
            done = len(outcomes) + len(errors)
            if done % 20 == 0 or done == len(records):
                print(json.dumps({"progress": done, "total": len(records), "errors": len(errors), "elapsedSeconds": round(time.monotonic() - started)}), flush=True)
    if errors:
        print(json.dumps({**report, "errors": errors, "metadataChanged": False}, ensure_ascii=False))
        return 1
    entries = [outcomes[file_id] for file_id in records]
    new_catalog = build_catalog(entries)
    baseline_ids = {item["id"] for item in read_json(root / "data/motifs-baseline.json")["motifs"]}
    if not baseline_ids.issubset({item["id"] for item in new_catalog}):
        raise ValueError("Refusing to commit metadata: original motif IDs are missing")
    changed = new_catalog != catalog or entries != old_manifest.get("motifs") or not compatible
    if changed:
        manifest = {"version": 1, "generatedAt": datetime.now(timezone.utc).isoformat(), "generator": GENERATOR,
                    "originalPolicy": "Drive files are referenced by stable ID and never changed. These are screen previews only.",
                    "motifs": entries}
        commit_metadata(root, new_catalog, manifest)
    summary = {**report, "actions": counters, "metadataChanged": changed, **validate(root), "elapsedSeconds": round(time.monotonic() - started)}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=Path("motifs.sources.json"))
    parser.add_argument("--cache", type=Path, default=ROOT.parent / "motif-preview-cache")
    parser.add_argument("--apply", action="store_true", help="Write local previews and metadata, never push/deploy")
    parser.add_argument("--discover", action="store_true", help="Discover configured Drive roots through read-only API")
    parser.add_argument("--refresh", action="store_true", help="Read source previews again, even without metadata changes")
    parser.add_argument("--validate", action="store_true", help="Validate all committed images without network")
    parser.add_argument("--verify-source-cache", type=Path, help="Also compare all pixels with the external source-preview cache")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        print("Import failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
