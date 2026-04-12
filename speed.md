Great question — the answer hinges on two key architectural differences: **what each method actually hashes**, and **process startup overhead**.

---

## The Core Difference: What Gets Hashed

| Method | What it hashes | Image decoding required? |
|---|---|---|
| **ExifTool `ImageDataHash`** | The **raw compressed bytes** of the image data segment (e.g., the JPEG entropy-coded scan data), skipping metadata segments | ❌ No decoding |
| **Pillow `tobytes()`** | The **fully decoded, decompressed pixel array** (raw RGB/RGBA values) | ✅ Full JPEG decode required |

This is the most important factor. ExifTool's `ImageDataHash` reads the file, skips the metadata segments (APP0, APP1/EXIF, etc.), and hashes the remaining compressed image bytes directly — **no decompression happens** [^3]. Pillow, on the other hand, must run the full JPEG decode pipeline: Huffman entropy decoding → inverse quantization → IDCT → colour conversion — before it can call `tobytes()` [^4]. For a typical 24MP RAW-derived JPEG, that's tens of millions of floating-point operations per image.

---

## Startup Overhead: ExifTool's Achilles Heel (and its fix)

ExifTool is written in Perl, and loading the Perl interpreter + the full `Image::ExifTool` library on every invocation is expensive. Benchmarks show that **startup overhead accounts for ~98.4% of execution time** when ExifTool is called once per file, yielding a **60× speedup** when files are batched in a single invocation [^1].

The fix is simple: **pass all files in one command**, or use `-stay_open` for persistent mode:

```bash
# Batch all files in one call (simplest)
exiftool -ImageDataHash -API ImageHashType=SHA256 /path/to/card1/*.jpg

# Or persistent mode (best for scripted/programmatic use)
exiftool -stay_open True -@ argfile.txt
```

With `-stay_open`, ExifTool loads once and processes commands from a pipe, eliminating startup cost entirely for every subsequent file [^5].

---

## Pillow's Overhead Profile

Pillow has **no per-process startup cost** (Python is already running), but it pays a **per-file CPU cost** for full JPEG decompression. For large files (e.g., 50 MP, 20+ MB JPEGs), this is significant. Additionally, vanilla Python is single-threaded due to the GIL, so you need `multiprocessing` to use multiple cores [^2]. Even then, each worker process must independently decode every image.

---

## Verdict: ExifTool `ImageDataHash` Wins in Batch

| Factor | ExifTool `ImageDataHash` | Pillow `tobytes()` |
|---|---|---|
| **Per-file CPU cost** | ✅ Low — hashes compressed bytes, no decode | ❌ High — full JPEG decode per file |
| **Startup overhead** | ⚠️ High per-process, but eliminated with batch/`-stay_open` | ✅ None (Python already running) |
| **Parallelism** | ⚠️ Single-threaded Perl (but I/O-bound, not CPU-bound) | ✅ Easy with `multiprocessing` |
| **Memory usage** | ✅ Low — no pixel buffer allocated | ❌ Higher — full decoded frame in RAM |
| **Batch winner** | ✅ **Faster** with proper batching | ❌ Slower for large/high-res files |

**In a real batch scenario (hundreds or thousands of camera files):**
- ExifTool with a single directory command or `-stay_open` will be **significantly faster** because it never decompresses a single pixel.
- Pillow's approach is CPU-bound and memory-hungry, especially for high-resolution RAW-derived JPEGs or TIFFs.

---

## Practical Recommendation

For your dual-card comparison use case, use ExifTool in a single batch call:

```bash
# Hash all files in both card directories at once
exiftool -ImageDataHash -API ImageHashType=SHA256 -r /card1/ /card2/ > hashes.txt
```

Or, if you need programmatic control in Python, use **PyExifTool** which wraps `-stay_open` automatically, giving you ExifTool's speed advantage from within Python:

```python
import exiftool

with exiftool.ExifToolHelper() as et:
    results = et.get_tags(file_list, tags=["ImageDataHash"], params=["-API", "ImageHashType=SHA256"])
```

This gives you the best of both worlds: Python scripting with ExifTool's no-decode hashing speed.

[^1]: [exiftool performance benchmark](https://exiftool.org/forum/index.php?topic=1402.0) (28%)
[^2]: [python - Batch image manipulation with PIL? - Stack Overflow](https://stackoverflow.com/questions/66282882/batch-image-manipulation-with-pil) (27%)
[^3]: [python - Compute hash of only the core image data (excluding metadata) for an image - Stack Overflow](https://stackoverflow.com/questions/10075065/compute-hash-of-only-the-core-image-data-excluding-metadata-for-an-image) (19%)
[^4]: [Need](https://arxiv.org/pdf/2501.13131) (15%)
[^5]: [Performance Optimization](https://deepwiki.com/exiftool/exiftool/10.1-performance-optimization) (11%)
