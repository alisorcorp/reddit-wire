import urllib.request
import os

files = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices.bin"
}

for name, url in files.items():
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, name)
    print(f"Downloaded {name}")
