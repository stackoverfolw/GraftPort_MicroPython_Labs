# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/15 上午11:17
# @Author  : 缪贵成
# @File    : tasksensor.py
# @Description : 读取 TCS34725 RGB 传感器，根据颜色判断播放对应频率音调（蜂鸣器版）
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import errno
import time
import _thread

# ======================================== 自定义类 ============================================

class SensorRGBSoundTask:
    """
    Functions:
        - Continuously collect RGB and print in real-time when the button is pressed
        - Stop collection and play sequence when released
        - Immediately stop playback and restart collection when button is pressed during playback
        - Adapted for buzzer.py driver (using play_tone method)
    """

    def __init__(self, touch_key=None, rgb_sensor=None, buzzer=None, enable_debug=False):
        self.rgb_sensor = rgb_sensor
        self.buzzer = buzzer  # Buzzer object (from Buzzer class in buzzer.py)
        self.enable_debug = enable_debug
        self.touch_key = touch_key

        # Status variables
        self._pressed = False
        self._reading = False
        self._sequence = []  # Store tuples of (frequency, duration in seconds)
        self._is_playing = False  # Playback status flag
        self._play_thread = None  # Playback thread handle

        # Configuration parameters
        self.COLLECT_INTERVAL_MS = 50
        self.DEBOUNCE_MS = 30
        self._last_key_time = 0
        self._last_pressed = False

    def _color_to_freq(self, r, g, b):
        """Convert RGB to frequency (keep original logic)"""
        if r > g and r > b:
            return 500, "RED"
        elif g > r and g > b:
            return 1000, "GREEN"
        elif b > r and b > g:
            return 1500, "BLUE"
        else:
            return 2000, "OTHER"

    def _stop_playback(self):
        """Stop buzzer sound (adapted for buzzer.py: stop by setting duty cycle to 0)"""
        if not self._is_playing:
            return False
        try:
            # Corresponding to stop logic in buzzer.py: duty_u16(0)
            self.buzzer.buzzer.duty_u16(0)
            self._is_playing = False
            print("[PLAY STOPPED] Buzzer stopped")
            return True
        except Exception as e:
            print(f"[STOP ERROR] Failed to stop buzzer: {e}")
            return False

    def immediate_stop(self):
        """Emergency stop: immediately terminate all playback and collection operations"""
        print("[EMERGENCY STOP] Executing emergency stop...")
        # Stop playback
        self._stop_playback()
        # Stop collection
        self._reading = False
        # Clear collection sequence
        self._sequence = []
        # Reset button status
        self._pressed = False
        self._last_pressed = False
        # Reset timestamp
        self._last_key_time = 0
        print("[EMERGENCY STOP COMPLETE] All operations terminated")

    def _play_async(self, sequence):
        """Asynchronously play sequence (adapted for buzzer.py's play_tone method)"""
        try:
            for freq, duration in sequence:
                if not self._is_playing:  # Check if need to stop midway
                    break
                # Use buzzer driver's play_tone method (frequency in Hz, duration in ms)
                self.buzzer.play_tone(freq, int(duration * 1000))  # Convert to milliseconds
                # Interval between notes (consistent with driver)
                time.sleep_ms(10)

                if not self._is_playing:
                    break

        except Exception as e:
            print(f"[PLAY ERROR] Buzzer playback failed: {e}")
        finally:
            # Ensure buzzer is off after playback
            self.buzzer.buzzer.duty_u16(0)
            self._is_playing = False
            print("[PLAY COMPLETED] Buzzer sequence finished")

    def tick(self):
        try:
            # 1. Check if hardware is ready (adapted for buzzer.py methods)
            if not self.rgb_sensor or not hasattr(self.rgb_sensor, "read"):
                print("[ERROR] RGB sensor not initialized or invalid")
                return
            if not self.touch_key:
                print("[ERROR] Touch key object not provided")
                return
            # Check if buzzer has play_tone method (core method in buzzer.py)
            if not self.buzzer or not hasattr(self.buzzer, "play_tone"):
                print("[ERROR] Buzzer object invalid (requires play_tone method)")
                return

            current_time = time.ticks_ms()

            # 2. Button debounce processing
            raw_pressed = self.touch_key.get_state()
            if raw_pressed != self._last_pressed:
                self._last_key_time = current_time
                self._last_pressed = raw_pressed
            pressed = raw_pressed if (current_time - self._last_key_time) > self.DEBOUNCE_MS else self._pressed
            self._pressed = pressed

            # 3. Button pressed during playback: stop playback and restart collection
            if self._is_playing and pressed:
                print("[KEY ACTION] Detected button press during playback → stopping buzzer")
                self._stop_playback()
                self._reading = True
                self._sequence = []
                print("[COLLECTION START] Playback stopped, starting new RGB collection")
                return

            # 4. Button pressed when not playing: start/continue collection
            if pressed and not self._is_playing:
                if not self._reading:
                    self._reading = True
                    self._sequence = []
                    print("[COLLECTION START] Button pressed, starting RGB collection")
                else:
                    if time.ticks_diff(current_time, self._last_key_time) >= self.COLLECT_INTERVAL_MS:
                        try:
                            r, g, b, c = self.rgb_sensor.read(raw=True)
                            freq, color = self._color_to_freq(r, g, b)
                            # Store (frequency, duration in seconds), convert to ms for play_tone later
                            self._sequence.append((freq, 0.5))
                            print(f"[COLLECTED DATA] R={r} G={g} B={b} → {color} (frequency: {freq}Hz)")
                            self._last_key_time = current_time
                        except OSError as e:
                            if e.errno == errno.EIO:
                                print(f"[COLLECTION ERROR] Sensor read failed, release button to retry: {e}")
                                self._reading = False
                                self._sequence = []
                            else:
                                print(f"[COLLECTION ERROR] Unknown read error: {e}")
                        except Exception as e:
                            print(f"[COLLECTION ERROR] Collection process exception: {e}")

            # 5. Button released: stop collection and start playback
            if not pressed and self._reading:
                self._reading = False
                print(f"[COLLECTION STOPPED] Button released, collected {len(self._sequence)} data points")

                if len(self._sequence) == 0:
                    print("[PLAYBACK INFO] No collected data, skipping playback")
                    return

                # Start asynchronous playback
                self._is_playing = True
                print(f"[PLAYBACK START] Starting playback of {len(self._sequence)} notes")
                self._play_thread = _thread.start_new_thread(self._play_async, (self._sequence,))

        except Exception as e:
            print(f"[SYSTEM ERROR] Main loop exception: {e}")
            # Call emergency stop on error
            self.immediate_stop()


# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================
