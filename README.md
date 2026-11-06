# TORCS webcam gesture controller

This Windows prototype uses two webcams:

- - The steering camera tracks both wrists. Tilting the line between your hands steers.
- The pedal camera tracks both ankles. After calibration, lifting the left-screen foot brakes and lifting the right-screen foot accelerates.

The controls default to TORCS' arrow keys. You can change them with command-line options if your installation uses different keys.

## Requirements

- 64-bit Python 3.14. The setup script creates the virtual environment and pip package cache inside this project folder.
- Two webcams, connected and not in use by another application.
- TORCS installed and configured to accept keyboard controls.

## Setup

Open PowerShell in this folder and run:

```powershell
.\setup.ps1
```

The script creates a local `.venv` and `.pip-cache`, installs the pinned computer-vision and input dependencies into that local environment, and downloads the hand and pose models into `models/`. It does not install TORCS.

## Start safely

First run the visual-only mode. It displays the two camera feeds and sends no keys:

```powershell
.\run.ps1
```

Place the foot camera so both ankles are visible, sit with both feet at rest, and press **C** while one of the preview windows is focused to calibrate. The app mirrors the previews. Move the foot on the left side of the preview upward to test braking, and the right-side foot upward to test acceleration. Turn your hands to test steering. Press **Q** in a preview window to exit.

If the cameras are listed in a different order, choose their indices:

```powershell
.\run.ps1 --steering-camera 1 --pedal-camera 0
```

## Enable live control

Only after the dry run behaves correctly, start live mode:

```powershell
.\run.ps1 --live
```

Live mode starts **disarmed** and sends no keys until you press **F9**. Focus the TORCS window, press **F9** to arm or disarm control, **F8** to calibrate the current neutral foot position, and **F10** to exit. If tracking is lost, the associated control returns to neutral. Closing the program releases any held keys.

Steering can be inverted if needed:

```powershell
.\run.ps1 --live --steer-invert
```

The pedal tracker uses ankle height as a simple proxy for pedal motion. Camera angle and lighting affect tracking; confirm the displayed meters in dry-run mode before arming live control.

## Tests

Run the dependency-free control mapping tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

The tests cover steering bounds, pedal calibration and bounds, safe neutral behavior, and arrow-key mapping.
