# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/15 下午
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : 传感器音频采集与播放任务（霍尔触发控制）
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 ==========================================

import time
import array
import micropython
from machine import Pin, PWM
import sys
import _thread

# ======================================== 全局配置参数 =============================================

BASE_FREQ = 800  # 基础频率
FREQ_RANGE = 700  # 频率范围
RECORD_INTERVAL_MS = 10  # 采样间隔(毫秒)
PLAY_DURATION_MS = 300  # 单个音符播放时长(毫秒)
MAX_RECORD_DURATION_MS = 10000  # 最大录音时长(毫秒)
MIN_RECORD_SAMPLES = 15  # 最小有效采样数
HALL_DEBOUNCE_MS = 100  # 霍尔传感器防抖时间(毫秒)
SAMPLE_PRINT_INTERVAL = 10  # 采样调试信息打印间隔

# 状态常量
STATE_IDLE = 0  # 空闲状态
STATE_RECORDING = 1  # 录音状态
STATE_PLAYING = 2  # 播放状态

# ======================================== 传感器任务类 =============================================

class SensorAudioTask:
    def __init__(self, hall_sensor, mic_sensor, buzzer, enable_debug=True):
        # 硬件对象
        self.hall = hall_sensor  # 霍尔传感器
        self.mic = mic_sensor  # 麦克风传感器
        self.buzzer = buzzer  # 蜂鸣器（音量由驱动固定）

        # 系统参数
        self.enable_debug = enable_debug
        self._is_running = True  # 运行状态标记

        # 状态变量
        self.system_state = STATE_IDLE
        self.record_buffer = array.array('H')  # 录音缓冲区
        self.play_index = 0  # 播放索引
        self.record_start_time = 0  # 录音开始时间
        self.last_operate_time = 0  # 最后操作时间
        self.adc_min = 65535  # 采样最小值
        self.adc_max = 0  # 采样最大值
        self._recording_lock = False  # 录音锁定标记
        self._hall_triggered = False  # 霍尔触发标记
        self._last_hall_state = None  # 上一次霍尔状态

        # 蜂鸣器PWM控制
        self.buzzer_pwm = None
        if hasattr(self.buzzer, 'buzzer') and isinstance(self.buzzer.buzzer, PWM):
            self.buzzer_pwm = self.buzzer.buzzer

        # 初始化硬件
        self._force_buzzer_stop()

        # 注册霍尔传感器回调（高优先级）
        try:
            self.hall.set_callback(None)
            self.hall.set_callback(lambda: setattr(self, '_hall_triggered', True))
            if self.enable_debug:
                print("[Hall Init] Callback bound successfully")
        except Exception as e:
            if self.enable_debug:
                print(f"[Hall Init Error] {e}")
            self.emergency_stop()

        # 配置退出处理机制
        self._setup_exit_handlers()

        if self.enable_debug:
            print(f"[SensorTask] Initialized successfully")

    # ======================================== 退出处理机制 =========================================
    def _setup_exit_handlers(self):
        """配置多重退出处理，确保异常情况下的安全关闭"""
        # 1. 系统退出回调
        try:
            sys.exitfunc = self._emergency_cleanup
        except AttributeError:
            if self.enable_debug:
                print("[Exit Handler] sys.exitfunc not supported")

        # 2. 线程异常处理
        try:
            _thread.excepthook = self._thread_exception_handler
        except AttributeError:
            if self.enable_debug:
                print("[Exit Handler] Thread excepthook not supported")

        # 3. 紧急异常缓冲区
        try:
            micropython.alloc_emergency_exception_buf(1024)
            if self.enable_debug:
                print("[Exit Handler] Emergency exception buffer allocated")
        except Exception as e:
            if self.enable_debug:
                print(f"[Exit Handler] Emergency buffer error: {e}")

    def _thread_exception_handler(self, args):
        """线程异常处理函数"""
        if self.enable_debug:
            print(f"[Thread Error] {args}")
        self.emergency_stop()

    def _emergency_cleanup(self):
        """程序退出前的紧急清理"""
        if self.enable_debug:
            print("\n[Emergency Cleanup] Executing final cleanup...")
        self._force_buzzer_stop()

    # ======================================== 蜂鸣器控制 =========================================
    def _force_buzzer_stop(self):
        """强制停止蜂鸣器（多重保障）"""
        try:
            # 1. 调用封装方法
            if hasattr(self.buzzer, 'off'):
                self.buzzer.off()
            elif hasattr(self.buzzer, 'stop'):
                self.buzzer.stop()

            # 2. 直接操作PWM
            if self.buzzer_pwm and isinstance(self.buzzer_pwm, PWM):
                self.buzzer_pwm.duty_u16(0)
                self.buzzer_pwm.freq(0)

            if self.enable_debug:
                print("[Buzzer] Forced stop")
        except Exception as e:
            if self.enable_debug:
                print(f"[Buzzer Stop Error] {e}")

    # ======================================== 紧急停止与恢复 =========================================
    def emergency_stop(self):
        """紧急停止所有操作，但保留恢复能力"""
        try:
            # 停止硬件
            self._force_buzzer_stop()

            # 重置核心状态（关键：允许后续恢复）
            self.record_buffer = array.array('H')
            self.play_index = 0
            self._recording_lock = False  # 解锁录音
            self.system_state = STATE_IDLE  # 回到空闲状态
            self._hall_triggered = False
            self._last_hall_state = self.hall.read()  # 重置霍尔状态

            if self.enable_debug:
                print("[Emergency Stop] Operations stopped - ready to resume")
        except Exception as e:
            # 最后的保障：确保蜂鸣器关闭
            try:
                self.buzzer_pwm.duty_u16(0)
            except:
                pass
            if self.enable_debug:
                print(f"[Emergency Stop Error] {e}")

    def resume(self):
        """手动恢复系统运行"""
        self._is_running = True
        self._recording_lock = False
        self._hall_triggered = False
        self.system_state = STATE_IDLE
        if self.enable_debug:
            print("[Resume] System resumed - ready to record")

    # ======================================== 霍尔传感器触发处理 =========================================
    def _process_hall_trigger(self):
        """处理霍尔传感器触发事件（优化灵敏度）"""
        if not self._hall_triggered:
            return
        self._hall_triggered = False  # 立即清除标志，避免漏检

        current_time = time.ticks_ms()
        # 非录音状态使用常规防抖
        if self.system_state != STATE_RECORDING:
            if time.ticks_diff(current_time, self.last_operate_time) < HALL_DEBOUNCE_MS:
                if self.enable_debug:
                    print("[Hall] Debounce filtered")
                return

        # 检测状态变化（边沿触发）
        hall_state = self.hall.read()
        state_changed = (hall_state != self._last_hall_state)
        self._last_hall_state = hall_state

        # 录音状态下快速响应
        if self.system_state == STATE_RECORDING:
            if state_changed and not hall_state:
                if self.enable_debug:
                    print(f"[Hall] Recording trigger (state={hall_state})")
                self.last_operate_time = current_time
                self._handle_hall_trigger()
            return

        # 非录音状态正常处理
        if not hall_state:
            if self.enable_debug:
                print(f"[Hall] Triggered (state={hall_state})")
            self.last_operate_time = current_time
            self._handle_hall_trigger()

    def _handle_hall_trigger(self):
        """处理霍尔触发后的状态切换"""
        try:
            if self.system_state == STATE_RECORDING:
                self._recording_lock = True
                if self.enable_debug:
                    print(f"[Hall] Stop recording (samples: {len(self.record_buffer)})")
                self.system_state = STATE_IDLE
                self._stop_recording(stop_reason="Hall Trigger")
                self._start_playing()
                return

            if self.system_state == STATE_IDLE:
                self._start_recording()
            elif self.system_state == STATE_PLAYING:
                self._stop_playing()
        except Exception as e:
            if self.enable_debug:
                print(f"[Hall Handle Error] {e}")
            self.emergency_stop()

    # ======================================== 录音逻辑 =========================================
    def _start_recording(self):
        """开始录音"""
        try:
            self.system_state = STATE_RECORDING
            self._recording_lock = False  # 确保解锁
            self.record_buffer = array.array('H')
            self.record_start_time = time.ticks_ms()
            self.adc_min = 65535
            self.adc_max = 0
            self._last_hall_state = self.hall.read()  # 重置霍尔状态

            if self.enable_debug:
                print("[Recording] Started: Swipe to stop")
        except Exception as e:
            if self.enable_debug:
                print(f"[Record Start Error] {e}")
            self.emergency_stop()

    def _stop_recording(self, stop_reason="Unknown"):
        """停止录音"""
        try:
            sample_count = len(self.record_buffer)

            if sample_count < MIN_RECORD_SAMPLES:
                if self.enable_debug:
                    print(f"[Recording] Insufficient samples ({sample_count}/{MIN_RECORD_SAMPLES})")
                return

            if self.enable_debug:
                print(f"[Recording] Stopped ({stop_reason}, {sample_count} samples)")
        except Exception as e:
            if self.enable_debug:
                print(f"[Record Stop Error] {e}")
            self.emergency_stop()

    # ======================================== 播放逻辑 =========================================
    def _start_playing(self):
        """开始播放录音"""
        try:
            if len(self.record_buffer) < MIN_RECORD_SAMPLES:
                if self.enable_debug:
                    print("[Playing] No valid data: Record again")
                self.system_state = STATE_IDLE
                return

            self.system_state = STATE_PLAYING
            self.play_index = 0
            adc_diff = self.adc_max - self.adc_min

            # 扩展动态范围（如果差异太小）
            if adc_diff < 50:
                expand = min(25, (65535 - self.adc_max) // 2, self.adc_min // 2)
                self.adc_min -= expand
                self.adc_max += expand

            if self.enable_debug:
                print(f"[Playing] Started ({len(self.record_buffer)} samples): Swipe to stop")
        except Exception as e:
            if self.enable_debug:
                print(f"[Play Start Error] {e}")
            self._stop_playing()

    def _stop_playing(self):
        """停止播放"""
        try:
            self._force_buzzer_stop()
            self.play_index = len(self.record_buffer)
            if self.enable_debug:
                print("[Playing] Stopped")
        except Exception as e:
            if self.enable_debug:
                print(f"[Play Stop Error] {e}")
        finally:
            self.system_state = STATE_IDLE

    # ======================================== 主循环 =========================================
    def tick(self):
        """主循环：处理所有状态和事件"""
        if not self._is_running:
            return True  # 即使暂停也保持循环，允许恢复

        try:
            # 优先处理霍尔触发
            self._process_hall_trigger()

            # 录音状态处理
            if self.system_state == STATE_RECORDING:
                current_time = time.ticks_ms()
                # 超时检查
                if time.ticks_diff(current_time, self.record_start_time) >= MAX_RECORD_DURATION_MS:
                    self._recording_lock = True
                    self._stop_recording(stop_reason="Timeout")
                    self._start_playing()
                    return True

                if self._recording_lock:
                    return True

                # 采样处理
                if time.ticks_diff(current_time, self.last_operate_time) >= RECORD_INTERVAL_MS:
                    adc_val = self.mic.read()
                    self.record_buffer.append(adc_val)
                    self.adc_min = min(self.adc_min, adc_val)
                    self.adc_max = max(self.adc_max, adc_val)

                    if self.enable_debug and len(self.record_buffer) % SAMPLE_PRINT_INTERVAL == 0:
                        print(f"[Recording] Collected {len(self.record_buffer)} samples")
                    self.last_operate_time = current_time

            # 播放状态处理
            elif self.system_state == STATE_PLAYING:
                if self.play_index >= len(self.record_buffer):
                    self._stop_playing()
                    return True

                # 计算播放频率
                current_adc = self.record_buffer[self.play_index]
                adc_diff = self.adc_max - self.adc_min
                normalized = 0.5 if adc_diff == 0 else (current_adc - self.adc_min) / adc_diff
                target_freq = int(BASE_FREQ - (FREQ_RANGE // 2) + normalized * FREQ_RANGE)
                target_freq = max(200, min(1200, target_freq))  # 频率限制

                # 控制蜂鸣器播放
                if self.buzzer_pwm and isinstance(self.buzzer_pwm, PWM):
                    self.buzzer_pwm.freq(target_freq)
                    self.buzzer_pwm.duty_u16(3277)  # 驱动固定5%音量（65535 * 5% ≈ 3277）
                else:
                    self.buzzer.play_tone(target_freq, PLAY_DURATION_MS)

                # 调试信息
                if self.enable_debug and self.play_index % 10 == 0:
                    print(f"[Playing] Index {self.play_index}: Frequency={target_freq}Hz")

                self.play_index += 1

            return True
        except Exception as e:
            if self.enable_debug:
                print(f"[Main Loop Error] {e}")
            self.emergency_stop()
            return True


# 初始化紧急异常缓冲区
micropython.alloc_emergency_exception_buf(1024)

# ======================================== 初始化配置 ============================================

# ======================================== 主程序 ===============================================
