Yes, it is absolutely possible to compare images by hash while ignoring EXIF data. Since the camera encodes the image once and writes the same bitstream to both cards simultaneously, the **pixel/image data will be byte-for-byte identical** — only the metadata wrapper differs. Several well-established methods exist to hash only the image data:

---

## Methods to Hash Image Data (Ignoring EXIF/Metadata)

### 1. ✅ ExifTool `ImageDataHash` (Recommended — Easiest & Most Reliable)

Since ExifTool **v12.58 (March 2023)**, there is a dedicated tag that hashes only the image data, explicitly ignoring all embedded metadata:

```bash
exiftool -ImageDataHash -API ImageHashType=SHA256 file1.jpg file2.jpg
```

**Supported formats:** JPEG, TIFF, PNG, CRW, CR3, MRW, RAF, X3F, IIQ, JP2, JXL, HEIC, AVIF, MOV/MP4, AVI, WAV, WEBP [^2]

You can also store the hash inside the file's XMP metadata for future reference:

```bash
exiftool -P -overwrite_original -API ImageHashType=SHA256 \
  -OriginalImageHashType=SHA256 "-OriginalImageHash<ImageDataHash" file.jpg
```

---

### 2. ImageMagick `identify -format "%#"` (Pixel-Level Hash)

ImageMagick's `identify` command with the `%#` format token computes a **SHA-256 hash of the decoded pixel data only**, completely ignoring metadata:

```bash
identify -format "%#:%f\n" image1.jpg image2.jpg
```

This is confirmed to produce identical hashes for images with the same pixels but different timestamps or EXIF data [^1]. It works across formats (JPEG, PNG, TIFF, BMP, GIF, etc.).

---

### 3. ExifTool Strip + `md5sum` (Pipe Method)

Strip all metadata in-memory and pipe the result to a hash tool — no temp files needed:

```bash
exiftool filename.jpg -all= -o - -b | md5sum -
```

> ⚠️ Some users report that ExifTool may leave residual metadata in certain cases. If that happens, use ImageMagick's `convert -strip` instead [^1]:

```bash
convert -strip filename.jpg - | md5sum
```

---

### 4. Python (Pillow) — Hash Raw Pixel Data

Pillow decodes the image and exposes raw pixel bytes, completely bypassing metadata:

```python
import hashlib
from PIL import Image

def hash_pixel_data(path: str) -> str:
    with Image.open(path) as img:
        rgb = img.convert("RGB")   # normalize color space
        return hashlib.sha256(rgb.tobytes()).hexdigest()

print(hash_pixel_data("card1/photo.jpg"))
print(hash_pixel_data("card2/photo.jpg"))
```

`tobytes()` returns a flat `[R, G, B, R, G, B, ...]` byte array — no metadata included [^3]. This works for any format Pillow supports (JPEG, PNG, TIFF, RAW via plugins, etc.).

---

## Summary Comparison

| Method | Tool | Formats | Notes |
|---|---|---|---|
| `exiftool -ImageDataHash` | ExifTool ≥12.58 | JPEG, TIFF, PNG, CR3, RAF, HEIC, AVIF, MP4, AVI… | Best option; purpose-built for this |
| `identify -format "%#"` | ImageMagick | All IM-supported formats | Hashes decoded pixels; very reliable |
| `exiftool -all= -o - -b \| md5sum` | ExifTool + md5sum | Most image formats | May leave residual metadata in edge cases |
| `convert -strip … \| md5sum` | ImageMagick | Most image formats | Strips metadata before hashing file bytes |
| `Image.open().tobytes()` | Python/Pillow | JPEG, PNG, TIFF, BMP, etc. | Hashes raw decoded pixels; very portable |

---

## Important Caveats

- **JPEG dual-card writes:** The camera compresses the image **once** and writes the same bitstream to both cards. The EXIF/metadata is a separate segment prepended to the file, so the pixel data (the JPEG entropy-coded scan data) should be **byte-for-byte identical** between the two cards. Any of the above methods will confirm this.
- **RAW formats (CR3, NEF, ARW, etc.):** The raw sensor data is also written identically; only the metadata block differs. ExifTool's `ImageDataHash` explicitly supports many RAW formats.
- **Avoid re-encoding:** Methods that decode pixels (Pillow `tobytes()`, ImageMagick `identify %#`) are safe but will produce a different hash than methods that hash the compressed data directly. Pick one method and use it consistently for both files.
- **Perceptual hashing** (e.g., `pHash`, `dHash`) is a different approach useful for *near-identical* images, but for your use case (exact duplicates from dual-card write), a cryptographic hash of the pixel or image data is the right tool.

[^1]: [Compare two image files for identical data - excluding metadata? - Software Recommendations Stack Exchange](https://softwarerecs.stackexchange.com/questions/51032/compare-two-image-files-for-identical-data-excluding-metadata) (56%)
[^2]: [python - Compute hash of only the core image data (excluding metadata) for an image - Stack Overflow](https://stackoverflow.com/questions/10075065/compute-hash-of-only-the-core-image-data-excluding-metadata-for-an-image) (25%)
[^3]: [How to Compute MD5 Hash of Core Image Data (Excluding EXIF Metadata): Finding EXIF Location in TIFF, JPG, PNG, and More Formats — pythontutorials.net](https://www.pythontutorials.net/blog/compute-hash-of-only-the-core-image-data-excluding-metadata-for-an-image/) (19%)
