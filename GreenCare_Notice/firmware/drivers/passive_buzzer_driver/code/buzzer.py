# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/8/28 上午11:22
# @Author  : 李清水
# @File    : buzzer.py
# @Description : 蜂鸣器驱动文件, v1.1.0 版本修改为蜂鸣器发声非阻塞式。
# @License : CC BY-NC 4.0

__version__ = "1.1.0"
__author__ = "李清水"
__license__ = "CC BY-NC 4.0"
__platform__ = "MicroPython v1.23"

# ======================================== 导入相关模块 =========================================

# 导入时间相关模块
import time
# 导入硬件相关的模块
from machine import Pin, PWM, Timer

# ======================================== 全局变量 ============================================

# 音符到频率的映射
NOTE_FREQS = {
    'C4': 261, 'D4': 293, 'E4': 329, 'F4': 349, 'G4': 392, 'A4': 440, 'B4': 493,
    'C5': 523, 'D5': 587, 'E5': 659, 'F5': 698, 'G5': 784, 'A5': 880, 'B5': 987,
    'C3': 130, 'D3': 146, 'E3': 164, 'F3': 174, 'G3': 196, 'A3': 220, 'B3': 246
}

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

class Buzzer:
    """
    蜂鸣器类，用于通过 PWM 驱动蜂鸣器播放音符和旋律。

    该类封装了蜂鸣器的控制逻辑，支持播放单个音符和一段旋律。
    通过 PWM 调节频率和占空比，可以实现不同音调和时长的声音效果。

    Attributes:
        buzzer (PWM): 蜂鸣器的 PWM 实例，用于控制频率和占空比。

    Methods:
        __init__(pin: int) -> None: 初始化蜂鸣器实例。
        play_tone(frequency: int, duration: int) -> None: 播放一个音符。
        play_melody(melody: list) -> None: 播放一段旋律。

    Notes:
        duty_u16=32768 表示 50% 占空比。
        melody 中每个元素为 (note, duration)，如 ('C4', 500)。
        NOTE_FREQS 字典需预定义，映射音符名称到频率。
        每个音符间默认有 10ms 间隔。

    ==========================================

    Buzzer class for driving a buzzer via PWM to play tones and melodies.

    This class encapsulates control logic for the buzzer, supporting
    both single tone playback and melody playback. By adjusting PWM
    frequency and duty cycle, different pitches and durations can be produced.

    Attributes:
        buzzer (PWM): PWM instance bound to buzzer for frequency and duty control.

    Methods:
        __init__(pin: int) -> None: Initialize buzzer instance.
        play_tone(frequency: int, duration: int) -> None: Play a single tone.
        play_melody(melody: list) -> None: Play a melody.

    Notes:
        duty_u16=32768 sets 50% duty cycle.
        melody elements are (note, duration), e.g., ('C4', 500).
        NOTE_FREQS dictionary must be predefined mapping note names to frequencies.
        Default gap of 10ms is inserted between notes.
    """

    def __init__(self, pin: int):
        """
        初始化蜂鸣器实例。

        Args:
            pin (int): 蜂鸣器连接的 GPIO 引脚编号。

        ==========================================

        Initialize buzzer instance.

        Args:
            pin (int): GPIO pin number connected to the buzzer.
        """
        # 设置PWM驱动蜂鸣器
        self.buzzer = PWM(Pin(pin))
        # 初始频率为2000
        self.buzzer.freq(2000)
        # 初始占空比为0
        self.buzzer.duty_u16(0)

        # 绑定定时器，用于非阻塞关闭
        self.timer = Timer(-1)
        # 当前旋律和索引
        self.melody = None
        self.idx = 0

    def play_tone(self, frequency: int, duration: int) -> None:
        """
        播放一个音符。

        Args:
            frequency (int): 音符频率（Hz）。
            duration (int): 持续时间（毫秒）。

        Returns:
            None

        ==========================================

        Play a single tone.

        Args:
            frequency (int): Frequency of the tone in Hz.
            duration (int): Duration of the tone in milliseconds.

        Returns:
            None
        """
        if frequency > 0:
            # 设置蜂鸣器的频率
            self.buzzer.freq(frequency)
            # 设置占空比为50%
            self.buzzer.duty_u16(32768)
        else:
            # 如果频率为0，则直接静音
            self.buzzer.duty_u16(0)

        # 定时器在 duration 毫秒后调用 stop()
        self.timer.init(mode=Timer.ONE_SHOT,
                        period=duration,
                        callback=lambda t: self.stop())

    def play_melody(self, melody: list) -> None:
        """
        播放一段旋律。

        Args:
            melody (list): 音符和持续时间的列表。
                           每个元素为元组 (note, duration)，
                           note 为音符名（如 'C4'），duration 为持续时间（毫秒）。

        Returns:
            None

        ==========================================

        Play a melody.

        Args:
            melody (list): List of (note, duration) tuples.
                           note is note name (e.g., 'C4'),
                           duration is duration in milliseconds.

        Returns:
            None
        """
        # 保存旋律和索引
        self.melody = melody
        self.idx = 0
        # 播放第一个音符
        self._play_next_note()

    def _play_next_note(self):
        """
        内部方法：播放旋律中的下一个音符。

        此方法由定时器回调触发，用于依次播放 melody 列表中的音符。
        每个音符结束后，会自动调用自身继续播放下一个音符，直到旋律结束。

        Returns:
            None

        ==========================================

        Internal method: play the next note in the melody.

        This method is triggered by the timer callback to sequentially
        play notes in the melody list. After finishing one note,
        it automatically schedules itself to play the next note,
        until the melody ends.

        Returns:
            None
        """
        if self.melody is None or self.idx >= len(self.melody):
            # 如果旋律播放结束，则停止
            self.stop()
            return

        # 取当前音符
        note, duration = self.melody[self.idx]
        # 查表得到频率
        frequency = NOTE_FREQS.get(note, 0)
        # 播放当前音符
        self.play_tone(frequency, duration)
        # 索引自增，准备下一个音符
        self.idx += 1

        # 在当前音符播放完成后 +10ms 间隔，再播下一个
        gap = duration + 10
        self.timer.init(mode=Timer.ONE_SHOT,
                        period=gap,
                        callback=lambda t: self._play_next_note())

    def stop(self) -> None:
        """
        立即停止播放。

        关闭蜂鸣器输出并释放定时器，
        清空当前旋律和索引，恢复到初始状态。

        Returns:
            None

        ==========================================

        Immediately stop playback.

        Turn off buzzer output and deinitialize the timer.
        Reset current melody and index to initial state.

        Returns:
            None
        """
        self.buzzer.duty_u16(0)
        self.timer.deinit()
        self.melody = None
        self.idx = 0

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================