import urllib.request
import os

files = {
    "kokoro-v0_19.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
    "voices.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
}

for name, url in files.items():
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, name)
    print(f"Downloaded {name}")
