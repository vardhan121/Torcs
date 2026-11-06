"""Two-camera gesture controller for TORCS."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path

from control import active_keys, pedal_levels, steering_from_wrists


KEY_NAMES = ("up", "down", "left", "right")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use a hand camera for steering and a foot camera for pedals."
    )
    parser.add_argument("--steering-camera", type=int, default=0)
    parser.add_argument("--pedal-camera", type=int, default=1)
    parser.add_argument("--live", action="store_true", help="Allow TORCS key input")
    parser.add_argument("--steer-invert", action="store_true")
    parser.add_argument("--max-steer-deg", type=float, default=35.0)
    parser.add_argument("--pedal-travel", type=float, default=0.10)
    parser.add_argument("--accel-key", choices=KEY_NAMES, default="up")
    parser.add_argument("--brake-key", choices=KEY_NAMES, default="down")
    parser.add_argument("--left-key", choices=KEY_NAMES, default="left")
    parser.add_argument("--right-key", choices=KEY_NAMES, default="right")
    args = parser.parse_args(argv)
    if args.steering_camera < 0 or args.pedal_camera < 0:
        parser.error("camera indices must be zero or greater")
    if args.steering_camera == args.pedal_camera:
        parser.error("steering and pedal cameras must use different indices")
    if args.max_steer_deg <= 0 or args.pedal_travel <= 0:
        parser.error("steering angle and pedal travel must be greater than zero")
    if len({args.accel_key, args.brake_key, args.left_key, args.right_key}) != 4:
        parser.error("each control must use a different key")
    return args


def load_dependencies(live: bool) -> tuple[object, object, object | None]:
    try:
        import cv2
        import mediapipe as mp
    except ImportError as error:
        raise RuntimeError(
            "Required packages are missing. Run setup.ps1, then start with run.ps1."
        ) from error

    keyboard = None
    if live:
        try:
            from pynput import keyboard as pynput_keyboard
        except ImportError as error:
            raise RuntimeError(
                "The pynput package is missing. Run setup.ps1 to install dependencies."
            ) from error
        keyboard = pynput_keyboard
    return cv2, mp, keyboard


def open_camera(cv2: object, index: int, label: str) -> object:
    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(
            f"Could not open the {label} camera (index {index}). "
            "Close other camera apps or try another camera index."
        )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera


def draw_meter(cv2: object, frame: object, label: str, value: float, y: int) -> None:
    width = 180
    cv2.putText(frame, label, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.rectangle(frame, (120, y - 16), (120 + width, y + 2), (80, 80, 80), 1)
    cv2.rectangle(
        frame,
        (121, y - 15),
        (121 + int(width * max(0.0, min(1.0, value))), y + 1),
        (0, 200, 80),
        -1,
    )


def run(args: argparse.Namespace) -> int:
    cv2, mp, keyboard = load_dependencies(args.live)
    steering_camera = open_camera(cv2, args.steering_camera, "steering")
    try:
        pedal_camera = open_camera(cv2, args.pedal_camera, "pedal")
    except Exception:
        steering_camera.release()
        raise

    models_directory = Path(__file__).resolve().parent / "models"
    hand_model = models_directory / "hand_landmarker.task"
    pose_model = models_directory / "pose_landmarker_lite.task"
    if not hand_model.is_file() or not pose_model.is_file():
        steering_camera.release()
        pedal_camera.release()
        raise RuntimeError("Model files are missing. Run setup.ps1 to download them.")
    try:
        hands = mp.tasks.vision.HandLandmarker.create_from_options(
            mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(hand_model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        pose = mp.tasks.vision.PoseLandmarker.create_from_options(
            mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(pose_model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
    except Exception:
        steering_camera.release()
        pedal_camera.release()
        if "hands" in locals():
            hands.close()
        raise

    key_map = (
        {
            "up": keyboard.Key.up,
            "down": keyboard.Key.down,
            "left": keyboard.Key.left,
            "right": keyboard.Key.right,
        }
        if args.live
        else {}
    )
    configured_keys = {
        "up": args.accel_key,
        "down": args.brake_key,
        "left": args.left_key,
        "right": args.right_key,
    }
    logical_to_physical = {
        "up": configured_keys["up"],
        "down": configured_keys["down"],
        "left": configured_keys["left"],
        "right": configured_keys["right"],
    }
    controller = keyboard.Controller() if args.live else None
    previous_keys: set[str] = set()
    neutral_y: tuple[float, float] | None = None
    armed = threading.Event()
    quit_requested = threading.Event()
    calibrate_requested = threading.Event()
    listener = None
    last_timestamp_ms = 0

    if args.live:
        def on_press(key: object) -> None:
            if key == keyboard.Key.f9:
                if armed.is_set():
                    armed.clear()
                else:
                    armed.set()
            elif key == keyboard.Key.f8:
                calibrate_requested.set()
            elif key == keyboard.Key.f10:
                quit_requested.set()

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

    try:
        while not quit_requested.is_set():
            steering_ok, steering_frame = steering_camera.read()
            pedal_ok, pedal_frame = pedal_camera.read()
            if not steering_ok or steering_frame is None:
                raise RuntimeError("Lost the steering camera feed.")
            if not pedal_ok or pedal_frame is None:
                raise RuntimeError("Lost the pedal camera feed.")

            steering_frame = cv2.flip(steering_frame, 1)
            pedal_frame = cv2.flip(pedal_frame, 1)
            timestamp_ms = max(time.monotonic_ns() // 1_000_000, last_timestamp_ms + 1)
            last_timestamp_ms = timestamp_ms
            hand_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(steering_frame, cv2.COLOR_BGR2RGB),
            )
            pose_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(pedal_frame, cv2.COLOR_BGR2RGB),
            )
            hand_result = hands.detect_for_video(hand_image, timestamp_ms)
            pose_result = pose.detect_for_video(pose_image, timestamp_ms)

            wrists: list[tuple[float, float]] = []
            for hand in hand_result.hand_landmarks:
                wrist = hand[0]
                wrists.append((wrist.x, wrist.y))
                cv2.circle(
                    steering_frame,
                    (int(wrist.x * steering_frame.shape[1]), int(wrist.y * steering_frame.shape[0])),
                    8,
                    (0, 255, 0),
                    -1,
                )
            steering = steering_from_wrists(wrists, args.max_steer_deg)
            if args.steer_invert:
                steering = -steering

            feet: list[tuple[float, float]] = []
            if pose_result.pose_landmarks:
                landmarks = pose_result.pose_landmarks[0]
                for index in (27, 28):
                    point = landmarks[index]
                    if point.visibility >= 0.5:
                        feet.append((point.x, point.y))
                        cv2.circle(
                            pedal_frame,
                            (int(point.x * pedal_frame.shape[1]), int(point.y * pedal_frame.shape[0])),
                            8,
                            (0, 255, 0),
                            -1,
                        )

            if calibrate_requested.is_set():
                if len(feet) >= 2:
                    ordered_feet = sorted(feet[:2], key=lambda point: point[0])
                    neutral_y = (ordered_feet[0][1], ordered_feet[1][1])
                    calibrate_requested.clear()
                else:
                    print("Calibration needs both ankles visible. Adjust the camera and try C again.")
                    calibrate_requested.clear()

            left_pedal, right_pedal = pedal_levels(feet, neutral_y, args.pedal_travel)
            brake, accelerator = left_pedal, right_pedal
            desired = active_keys(steering, accelerator, brake)
            output_keys = {
                logical_to_physical[key] for key in desired
            } if args.live and armed.is_set() else set()

            if controller is not None:
                for key_name in previous_keys - output_keys:
                    controller.release(key_map[key_name])
                for key_name in output_keys - previous_keys:
                    controller.press(key_map[key_name])
            previous_keys = output_keys

            mode = (
                "LIVE / ARMED"
                if armed.is_set()
                else "LIVE / DISARMED"
                if args.live
                else "DRY RUN - no keys sent"
            )
            cv2.putText(
                steering_frame,
                mode,
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255) if armed.is_set() else (0, 200, 255),
                2,
            )
            draw_meter(cv2, steering_frame, "Steer", abs(steering), 62)
            pedal_status = "Calibrated" if neutral_y is not None else "Press C/F8 to calibrate"
            cv2.putText(pedal_frame, pedal_status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 2)
            draw_meter(cv2, pedal_frame, "Brake (left)", left_pedal, 62)
            draw_meter(cv2, pedal_frame, "Accel (right)", right_pedal, 94)
            cv2.imshow("TORCS gesture control - hands", steering_frame)
            cv2.imshow("TORCS gesture control - feet", pedal_frame)

            if not args.live:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("c"):
                    if len(feet) >= 2:
                        ordered_feet = sorted(feet[:2], key=lambda point: point[0])
                        neutral_y = (ordered_feet[0][1], ordered_feet[1][1])
                    else:
                        print("Calibration needs both ankles visible. Adjust the camera and try C again.")
                elif key == ord("q"):
                    break

    finally:
        if controller is not None:
            for key_name in previous_keys:
                controller.release(key_map[key_name])
        if listener is not None:
            listener.stop()
        hands.close()
        pose.close()
        steering_camera.release()
        pedal_camera.release()
        cv2.destroyAllWindows()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
