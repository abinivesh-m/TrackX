import asyncio, base64, json, time
import websockets

CAMERA_ID = "CAM_01"
URI = f"ws://localhost:8000/api/v1/observations/live-stream/{CAMERA_ID}"
MAX_SECONDS = 45
MAX_FRAMES = 20

async def main():
    print(f"Connecting to {URI} ...")
    frames_received = 0
    max_vehicles_seen = 0
    saved_frame = False
    start = time.time()
    try:
        async with websockets.connect(URI, max_size=20_000_000) as ws:
            while True:
                elapsed = time.time() - start
                if elapsed > MAX_SECONDS or frames_received >= MAX_FRAMES:
                    print(f"\nStopping after {elapsed:.1f}s / {frames_received} frame(s).")
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(1.0, MAX_SECONDS - elapsed))
                except asyncio.TimeoutError:
                    print("\nNo message received in time - stopping.")
                    break
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "started":
                    print("STARTED:", json.dumps(msg, indent=2))
                elif t == "frame":
                    frames_received += 1
                    v = msg.get("vehicles_in_frame", 0)
                    max_vehicles_seen = max(max_vehicles_seen, v)
                    print(f"FRAME #{msg.get('frame_idx')}: vehicles_in_frame={v} "
                          f"fps_so_far={msg.get('fps_so_far')} elapsed={msg.get('elapsed_seconds')}")
                    if not saved_frame and msg.get("jpeg_b64"):
                        with open("trackx_live_frame_proof.jpg", "wb") as f:
                            f.write(base64.b64decode(msg["jpeg_b64"]))
                        saved_frame = True
                        print("  -> saved as trackx_live_frame_proof.jpg")
                elif t == "done":
                    print("DONE:", json.dumps(msg, indent=2))
                    break
                elif t == "error":
                    print("ERROR:", json.dumps(msg, indent=2))
                    break
                else:
                    print("OTHER:", msg)
    except Exception as e:
        print("CONNECTION FAILED:", type(e).__name__, e)

    print("\n=== SUMMARY ===")
    print(f"Frames received: {frames_received}")
    print(f"Max vehicles_in_frame seen: {max_vehicles_seen}")
    print(f"Frame image saved: {saved_frame} (trackx_live_frame_proof.jpg)")

asyncio.run(main())
