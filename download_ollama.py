import urllib.request, time, sys
last_print_time = 0
start_time = time.time()

def reporthook(count, block_size, total_size):
    global last_print_time, start_time
    now = time.time()
    if now - last_print_time >= 3:
        duration = now - start_time
        progress_size = count * block_size
        speed = (progress_size / 1024) / duration if duration > 0 else 0
        percent = (progress_size / total_size) * 100 if total_size > 0 else 0
        print(f"Progress: {percent:.1f}% | {progress_size / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB | Speed: {speed:.1f} KB/s", flush=True)
        last_print_time = now

print('Starting download...')
urllib.request.urlretrieve('https://ollama.com/download/OllamaSetup.exe', 'OllamaSetup.exe', reporthook)
print('Download complete!')
