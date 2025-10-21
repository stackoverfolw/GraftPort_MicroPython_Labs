# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14 下午11:17
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : 传感器任务
# @License : CC BY-NC 4.0


# ======================================== 导入相关模块 ==========================================

import time
import array
import micropython
from machine import Pin, PWM
import sys


# ======================================== 全局变量 =============================================

VOLUME_PERCENT = 50
BASE_FREQ = 800
FREQ_RANGE = 700
RECORD_INTERVAL_MS = 10
PLAY_DURATION_MS = 300
MAX_RECORD_DURATION_MS = 10000
MIN_RECORD_SAMPLES = 15
HALL_DEBOUNCE_MS = 200
SAMPLE_PRINT_INTERVAL = 10

# State Constants
STATE_IDLE = 0
STATE_RECORDING = 1
STATE_PLAYING = 2

# ======================================== 功能函数 =============================================

# ======================================== 自定义类 =============================================


class SensorAudioTask:
    def __init__(self, hall_sensor, mic_sensor, speaker_pwm, oled=None, enable_debug=True):
        self.hall = hall_sensor
        self.mic = mic_sensor
        self.speaker = speaker_pwm  # LMSpeaker Instance
        self.oled = oled
        self.enable_debug = enable_debug

        # State Variables
        self.system_state = STATE_IDLE
        self.record_buffer = array.array('H')
        self.play_index = 0
        self.record_start_time = 0
        self.last_operate_time = 0
        self.adc_min = 65535
        self.adc_max = 0
        self._recording_lock = False
        self._hall_triggered = False  # Hall Trigger Flag

        # Save Speaker PWM Info (for low-level force stop)
        self.speaker_pwm = None
        if hasattr(self.speaker, 'pwm'):
            self.speaker_pwm = self.speaker.pwm

        # Initialize Speaker (Force Mute)
        self._force_speaker_stop()

        # Fix 1: Adapt to HallSensor without 'irq' method, use callback instead
        try:
            # Unbind first to avoid residual callback
            self.hall.set_callback(None)
            # Bind Hall sensor callback (use sensor-supported method)
            self.hall.set_callback(self._hall_callback)
            if self.enable_debug:
                print("[Hall Init] Callback method bound successfully")
        except Exception as e:
            if self.enable_debug:
                print(f"[Hall Init Error] {e}")

        # Fix 2: Adapt to environments without 'sys.exitfunc'
        try:
            # Try to register exit hook (compatible with supported systems)
            sys.exitfunc = self._emergency_cleanup
        except AttributeError:
            if self.enable_debug:
                print(
                    "[System Note] Current environment does not support exitfunc, other methods will be used to ensure safe exit")

        if self.enable_debug:
            print(f"[SensorTask] Initialization completed: Volume={VOLUME_PERCENT}%")
        self._update_oled("Ready: Swipe coin to record")

    # ======================================== Hall Trigger Logic Fix =========================================
    def _hall_callback(self):
        """Hall Sensor Callback (adapt to sensor-supported interface)"""
        # Only set flag in callback to avoid complex operations
        self._hall_triggered = True

    def _process_hall_trigger(self):
        """Process Hall Trigger (executed in main loop to avoid callback block)"""
        if not self._hall_triggered:
            return
        self._hall_triggered = False  # Clear flag

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_operate_time) < HALL_DEBOUNCE_MS:
            if self.enable_debug:
                print("[Hall Trigger] Debounce filter applied")
            return
        self.last_operate_time = current_time

        # Read Hall sensor state
        hall_state = self.hall.read()
        if self.enable_debug:
            print(f"[Hall Trigger] State={hall_state}, Current system state={self.system_state}")

        if not hall_state:  # Low-level active
            self._handle_hall_trigger()

    def _handle_hall_trigger(self):
        """State Switch Logic"""
        try:
            if self.system_state == STATE_IDLE:
                self._start_recording()
            elif self.system_state == STATE_RECORDING:
                # 2nd Trigger: Force stop recording
                self._recording_lock = True
                if self.enable_debug:
                    print(f"[Hall Trigger] Stop recording (Current sample count: {len(self.record_buffer)})")
                self._stop_recording(stop_reason="Hall Trigger")
                self._start_playing()
            elif self.system_state == STATE_PLAYING:
                self._stop_playing()
        except Exception as e:
            if self.enable_debug:
                print(f"[State Switch Error] {e}")
            self.emergency_stop()

    # ======================================== Exit Handling Fix =========================================
    def _emergency_cleanup(self):
        """Emergency Cleanup: Force stop speaker"""
        if self.enable_debug:
            print("\n[Emergency Exit] Executing mute operation...")
        self._force_speaker_stop()
        if self.oled:
            try:
                self.oled.fill(0)
                self.oled.text("Force stopped", 0, 10)
                self.oled.show()
            except:
                pass

    def _force_speaker_stop(self):
        """Low-level Force Stop Speaker"""
        try:
            # 1. Call wrapped method
            self.speaker.stop()
            # 2. Directly operate PWM (if exists)
            if self.speaker_pwm and isinstance(self.speaker_pwm, PWM):
                self.speaker_pwm.duty(0)
                self.speaker_pwm.freq(0)
            if self.enable_debug:
                print("[Force Mute] Speaker stopped successfully")
        except Exception as e:
            if self.enable_debug:
                print(f"[Force Mute Error] {e}")

    # ======================================== Other Methods =========================================
    def _start_recording(self):
        try:
            self.system_state = STATE_RECORDING
            self._recording_lock = False
            self.record_buffer = array.array('H')
            self.record_start_time = time.ticks_ms()
            self.adc_min = 65535
            self.adc_max = 0

            if self.enable_debug:
                print("[Recording] Started (wait for 2nd Hall trigger to stop)")
            self._update_oled("Recording: Swipe again to stop")
        except Exception as e:
            if self.enable_debug:
                print(f"[Recording Start Error] {e}")
            self.emergency_stop()

    def _stop_recording(self, stop_reason="Unknown"):
        try:
            self.system_state = STATE_IDLE
            sample_count = len(self.record_buffer)

            if sample_count < MIN_RECORD_SAMPLES:
                if self.enable_debug:
                    print(f"[Recording] Insufficient samples ({sample_count} samples, need ≥{MIN_RECORD_SAMPLES})")
                self._update_oled("Ready: Swipe coin to record")
                return

            if self.enable_debug:
                print(f"[Recording] Stopped (Reason: {stop_reason}, {sample_count} samples)")
        except Exception as e:
            if self.enable_debug:
                print(f"[Recording Stop Error] {e}")
            self.emergency_stop()

    def _start_playing(self):
        try:
            if len(self.record_buffer) < MIN_RECORD_SAMPLES:
                if self.enable_debug:
                    print("[Playing] No valid recording data")
                self._update_oled("No valid recording: Record again")
                return

            self.system_state = STATE_PLAYING
            self.play_index = 0
            adc_diff = self.adc_max - self.adc_min

            if adc_diff < 50:
                expand = min(25, (65535 - self.adc_max) // 2, self.adc_min // 2)
                self.adc_min -= expand
                self.adc_max += expand

            if self.enable_debug:
                print(f"[Playing] Started (Sample count: {len(self.record_buffer)})")
            self._update_oled("Playing: Swipe again to stop")
        except Exception as e:
            if self.enable_debug:
                print(f"[Playing Start Error] {e}")
            self._stop_playing()

    def _stop_playing(self):
        try:
            self._force_speaker_stop()
            self.play_index = len(self.record_buffer)
            if self.enable_debug:
                print("[Playing] Stopped successfully")
        except Exception as e:
            if self.enable_debug:
                print(f"[Playing Stop Error] {e}")
        finally:
            self.system_state = STATE_IDLE
            self._update_oled("Ready: Swipe coin to record")

    def emergency_stop(self):
        self._force_speaker_stop()
        self.record_buffer = array.array('H')
        self.play_index = 0
        self._recording_lock = True
        self.system_state = STATE_IDLE
        self._update_oled("Emergency Stop: Please retry")
        if self.enable_debug:
            print("[Emergency Stop] System reset completed")

    def _update_oled(self, text):
        if self.oled:
            try:
                self.oled.fill(0)
                self.oled.text(text, 0, 10)
                self.oled.show()
            except Exception as e:
                if self.enable_debug:
                    print(f"[OLED Error] {e}")

    def tick(self):
        """Main Loop: Add Hall trigger processing"""
        # Process Hall trigger first (fix 2nd trigger issue)
        self._process_hall_trigger()

        try:
            if self.system_state == STATE_RECORDING:
                current_time = time.ticks_ms()
                # Timeout stop
                if time.ticks_diff(current_time, self.record_start_time) >= MAX_RECORD_DURATION_MS:
                    if self.enable_debug:
                        print(f"[Recording] Timeout stopped (10 seconds)")
                    self._recording_lock = True
                    self._stop_recording(stop_reason="Timeout")
                    self._start_playing()
                    return

                if self._recording_lock:
                    return

                # Sampling logic
                if time.ticks_diff(current_time, self.last_operate_time) >= RECORD_INTERVAL_MS:
                    adc_val = self.mic.read()
                    self.record_buffer.append(adc_val)
                    self.adc_min = min(self.adc_min, adc_val)
                    self.adc_max = max(self.adc_max, adc_val)

                    if self.enable_debug and len(self.record_buffer) % SAMPLE_PRINT_INTERVAL == 0:
                        print(f"[Recording] Collected {len(self.record_buffer)} samples")
                    self.last_operate_time = current_time

            elif self.system_state == STATE_PLAYING:
                if self.play_index >= len(self.record_buffer):
                    self._stop_playing()
                    return

                current_adc = self.record_buffer[self.play_index]
                adc_diff = self.adc_max - self.adc_min
                normalized = 0.5 if adc_diff == 0 else (current_adc - self.adc_min) / adc_diff
                target_freq = int(BASE_FREQ - (FREQ_RANGE // 2) + normalized * FREQ_RANGE)
                target_freq = max(200, min(1200, target_freq))

                self.speaker.play_tone(frequency=target_freq, duration=PLAY_DURATION_MS / 1000)

                if self.enable_debug and self.play_index % 10 == 0:
                    print(f"[Playing] Index {self.play_index}: Frequency={target_freq}Hz")

                self.play_index += 1

        except Exception as e:
            if self.enable_debug:
                print(f"[Main Loop Error] {e}")
            self.emergency_stop()


# Initialize emergency exception buffer
micropython.alloc_emergency_exception_buf(100)

# ======================================== 初始化配置 ============================================

# ======================================== 主程序 ===============================================
