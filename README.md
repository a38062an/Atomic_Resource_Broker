# Atomic Resource Broker

This is a client application I built to manage shared resources across two different services (Hotel and Band). The main goal is to make sure we either get slots from *both* services or *neither*—no half-bookings allowed.

## How It Works

The app talks to two external APIs. Since these APIs can be slow or unreliable, I built the client to be robust:
*   **Atomic Transactions**: If I book a hotel but the band fails, the app automatically cancels the hotel to keep things clean.
*   **No Freezing**: The UI runs separately from the network calls (using threading), so the window doesn't hang while waiting for the server.
*   **Rate Limiting**: It respects the 1-second delay rule so we don't get blocked by the server.

## Project Structure

I split the code into a few files to keep it organized:

*   **`booking_gui.py`**: This is the main file. Run this to start the app. It handles the GUI.
*   **`booking_service.py`**: This is where the actual logic lives (finding slots, booking, cancelling).
*   **`reservation_api.py`**: The wrapper that talks to the real servers.
*   **`mock_reservation_api.py`**: A fake version of the API I wrote so you can test the app without needing a real server or API keys.
*   **`config_manager.py`**: Handles loading the `api.ini` config file.

## How to Run

### 1. Demo Mode (No Keys Needed)
If you just want to see it working, I added a demo mode. It uses a mock API that simulates the real thing.

```bash
python3 booking_gui.py --demo
```

### 2. Real Mode
To use the real API, make sure you have your `api.ini` file set up with the URLs and keys, then run:

```bash
python3 booking_gui.py
```

### 3. CLI Test
I also wrote a quick script to test the logic in the terminal without the GUI:

```bash
python3 demo.py
```
