# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/10 下午5:15
# @Author  : 缪贵成
# @File    : tasksensor.py
# @Description : 读取 TCS34725 RGB 传感器，根据颜色判断播放对应频率音调
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import errno
import time
import _thread  # 用于异步播放，避免阻塞按键检测


# ======================================== 自定义类 ============================================

class SensorRGBSoundTask:
    """
    功能：
        - 按键按下时持续采集 RGB 并实时打印
        - 松开后停止采集并播放序列
        - 播放时按下按键立即停止播放并重新采集
        - 仅使用LMSpeaker支持的方法（play_sequence()和stop()）
    """

    def __init__(self, touch_key=None, rgb_sensor=None, speaker=None, enable_debug=False):
        self.rgb_sensor = rgb_sensor
        self.speaker = speaker
        self.enable_debug = enable_debug
        self.touch_key = touch_key

        # 状态变量（全部显式初始化）
        self._pressed = False
        self._reading = False
        self._sequence = []
        self._is_playing = False  # 核心播放状态标记
        self._play_thread = None  # 播放线程句柄

        # 配置参数
        self.COLLECT_INTERVAL_MS = 50
        self.DEBOUNCE_MS = 30
        self._last_key_time = 0
        self._last_pressed = False

    def _color_to_freq(self, r, g, b):
        """RGB转频率（保持原有逻辑）"""
        if r > g and r > b:
            return 500, "RED"
        elif g > r and g > b:
            return 1000, "GREEN"
        elif b > r and b > g:
            return 1500, "BLUE"
        else:
            return 2000, "OTHER"

    def _stop_playback(self):
        """停止播放（仅使用LMSpeaker的stop()方法）"""
        if not self._is_playing:
            return False
        try:
            # 调用扬声器的stop方法
            self.speaker.stop()
            self._is_playing = False
            print("[PLAY STOPPED] 播放已被停止（通过按键或完成）")
            return True
        except Exception as e:
            print(f"[STOP ERROR] 停止播放失败: {e}")
            return False

    def _play_async(self, sequence):
        """异步播放序列（在单独线程中执行，避免阻塞）"""
        try:
            # 调用扬声器的play_sequence方法（无额外参数）
            self.speaker.play_sequence(sequence)
        except Exception as e:
            print(f"[PLAY ERROR] 播放序列失败: {e}")
        finally:
            # 播放结束后更新状态
            self._is_playing = False
            print("[PLAY COMPLETED] 播放序列已结束")

    def tick(self):
        try:
            # 1. 检查硬件是否就绪（明确报错）
            if not self.rgb_sensor or not hasattr(self.rgb_sensor, "read"):
                print("[ERROR] RGB传感器未初始化或无效")
                return
            if not self.touch_key:
                print("[ERROR] 触摸按键对象未传入")
                return
            if not self.speaker or not hasattr(self.speaker, "play_sequence") or not hasattr(self.speaker, "stop"):
                print("[ERROR] 扬声器对象无效（需支持play_sequence和stop方法）")
                return

            current_time = time.ticks_ms()

            # 2. 按键防抖处理
            raw_pressed = self.touch_key.get_state()
            if raw_pressed != self._last_pressed:
                self._last_key_time = current_time
                self._last_pressed = raw_pressed
            # 防抖后确定按键状态
            pressed = raw_pressed if (current_time - self._last_key_time) > self.DEBOUNCE_MS else self._pressed
            self._pressed = pressed

            # 3. 播放中按下按键：最高优先级处理
            if self._is_playing and pressed:
                print("[KEY ACTION] 检测到播放中按键按下 → 准备停止播放")
                # 停止当前播放
                self._stop_playback()
                # 立即开始新采集
                self._reading = True
                self._sequence = []
                print("[采集启动] 已停止播放，开始新的RGB采集")
                return

            # 4. 未播放时按下按键：开始/继续采集
            if pressed and not self._is_playing:
                if not self._reading:
                    # 首次按下：初始化采集
                    self._reading = True
                    self._sequence = []
                    print("[采集启动] 按键按下，开始RGB采集")
                else:
                    # 持续按住：定时采集数据
                    if time.ticks_diff(current_time, self._last_key_time) >= self.COLLECT_INTERVAL_MS:
                        try:
                            r, g, b, c = self.rgb_sensor.read(raw=True)
                            freq, color = self._color_to_freq(r, g, b)
                            self._sequence.append((freq, 0.5))  # 保持原有格式
                            print(f"[采集数据] R={r} G={g} B={b} → {color} (频率: {freq}Hz)")
                            self._last_key_time = current_time  # 重置采集计时器
                        except OSError as e:
                            if e.errno == errno.EIO:
                                print(f"[采集错误] 传感器读取失败，请松开按键重试: {e}")
                                self._reading = False
                                self._sequence = []
                            else:
                                print(f"[采集错误] 未知读取错误: {e}")
                        except Exception as e:
                            print(f"[采集错误] 采集过程异常: {e}")

            # 5. 松开按键：停止采集并启动播放
            if not pressed and self._reading:
                self._reading = False
                print(f"[采集结束] 按键松开，共采集 {len(self._sequence)} 个数据")

                if len(self._sequence) == 0:
                    print("[播放信息] 无采集数据，跳过播放")
                    return

                # 启动异步播放（避免阻塞）
                self._is_playing = True
                print(f"[播放启动] 开始播放 {len(self._sequence)} 个音符")
                # 在新线程中执行播放，确保主循环能继续检测按键
                self._play_thread = _thread.start_new_thread(self._play_async, (self._sequence,))

        except Exception as e:
            print(f"[系统错误] 主循环异常: {e}")
            self._stop_playback()  # 出错时强制停止播放
            self._reading = False  # 重置采集状态
            self._sequence = []

# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ============================================

