# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/10 下午4:32   
# @Author  : 李清水            
# @File    : sensor_task.py       
# @Description : 每 200ms 读取超声波模块的测距距离、三点均值滤波、根据距离设置 LED 占空比与蜂鸣器频率（可调映射），支持 DEBUG 输出
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# 导入队列相关模块
from collections import deque

# 导入驱动相关模块
try:
    from ..drivers.passive_buzzer_driver import NOTE_FREQS
except Exception:
    # 音符到频率的映射
    NOTE_FREQS = {
        'C4': 261, 'D4': 293, 'E4': 329, 'F4': 349, 'G4': 392, 'A4': 440, 'B4': 493,
        'C5': 523, 'D5': 587, 'E5': 659, 'F5': 698, 'G5': 784, 'A5': 880, 'B5': 987,
        'C3': 130, 'D3': 146, 'E3': 164, 'F3': 174, 'G3': 196, 'A3': 220, 'B3': 246
    }

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

class SensorBuzzerLedTask:
    """
    任务1：每 200ms 运行一次
    构造参数：
        rcwl: RCWL9623 实例，提供 read_distance()
        buzzer: Buzzer 实例，提供 play_tone(frequency,duration) / play_melody(...)
        piranha_led: PiranhaLED 实例，提供 set_brightness(percent)/on()/off()
        enable_debug, min_dist, max_dist
    """

    def __init__(self, rcwl, buzzer, piranha_led,
                 enable_debug=False, min_dist=25, max_dist=250):
        # rcwl.read_distance() 用于读取当前距离（cm 或 None）
        self.rcwl = rcwl
        # buzzer.play_tone(freq, dur) 用于播放音符（或用作静音退路）
        self.buzzer = buzzer
        # piranha_led.set_brightness(percent) 用于设置亮度（0..100）
        self.piranha_led = piranha_led

        self.enable_debug = enable_debug
        # 映射区间（用于 LED 亮度线性映射）
        self.min_dist = min_dist
        self.max_dist = max_dist

        # 三点均值滤波缓冲（最多保存 3 个最近有效读数）
        self._buf = deque((), 3)
        # 上次被接受的有效读数（用于异常跳变判断与在无缓冲时作为 fallback）
        self._last_valid = None
        # 当前对外输出的亮度（记录方便在 None 情况保持不变）
        self._out_duty = 0
        # 最近一次原始读取值（用于 debug / 外部检查）
        self.raw = None
        # 被忽略的异常读数次数
        self._outlier_cnt = 0

        # 动态生成使用的音符序列（按频率从高到低）
        # 思路：
        # - 从 NOTE_FREQS 中取出所有 (note, freq)，按 freq 从高到低排序（越高的频率对应越近的距离）
        # - 把 min_dist..max_dist 区间平均分成 N 段（N 为音符数量），每段对应一个音符
        # - 最后追加 (9999, 'OFF') 表示超出最大阈值时静音
        try:
            sorted_notes = sorted(NOTE_FREQS.items(), key=lambda kv: kv[1], reverse=True)
            notes_order = [n for n, f in sorted_notes]
        except Exception:
            # 若 NOTE_FREQS 异常（极少数情况），用一个预设音符序列作为兜底
            notes_order = ['A5', 'G5', 'E5', 'C5', 'B4', 'A4', 'G4', 'F4',
                           'E4', 'D4', 'C4', 'B3', 'A3', 'G3', 'F3', 'E3', 'D3', 'C3']

        # 构建 note_map（阈值，音符）
        self.note_map = []
        span = self.max_dist - self.min_dist
        # 可能为负/0（需兜底）
        if span <= 0 or len(notes_order) == 0:
            self.note_map = [
                (40, 'A5'),
                (80, 'G5'),
                (120, 'E5'),
                (180, 'C5'),
                (9999, 'OFF'),
            ]
        else:
            # per: 每段的距离宽度（浮点），可能小于 1（当 span < len(notes_order) 时）
            per = float(span) / len(notes_order)
            # i 从 0 开始，阈值取 min_dist + (i+1)*per，表示第 (i) 个音符的上界
            for i, note in enumerate(notes_order):
                thr = int(self.min_dist + (i + 1) * per)
                self.note_map.append((thr, note))
            # 末尾静音分支（超出所有阈值）
            self.note_map.append((9999, 'OFF'))

    def _choose_note(self, distance):
        """
        给定 distance 返回对应音符（字符串），distance 为 None 返回 'OFF'。
        note_map 中按阈值从小到大排列（近->远）。
        """
        if distance is None:
            return 'OFF'
        for thr, note in self.note_map:
            if distance <= thr:
                return note
        return 'OFF'

    def _compute_led_duty(self, distance):
        """
        将 distance 映射到 0..100 的占空比，越近越亮。
        - 当 distance 为 None：返回上次输出的占空比（保持不变）
        - 对 distance 做裁剪：小于 min_dist -> min_dist；大于 max_dist -> max_dist
        - 线性映射：duty = int((max_dist - d) * 100 / span)
        """
        if distance is None:
            return self._out_duty

        d = max(self.min_dist, min(distance, self.max_dist))
        span = self.max_dist - self.min_dist
        if span <= 0:
            return 0

        # 归一化距离 (0..1)，越近越大
        norm = (self.max_dist - d) / span

        # 指数非线性映射
        exponent = 5  # 指数越大，近距离越快接近 100%
        duty = int((norm ** exponent) * 100)

        # 限制范围
        duty = max(0, min(duty, 100))
        return duty

    # 硬件适配
    def _set_led_duty(self, percent):
        """
        统一调用 LED 实例设置亮度。只尝试调用 piranha_led.set_brightness(percent)。
        捕获异常并在 enable_debug=True 时打印错误信息。
        """
        if self.piranha_led is None:
            return
        try:
            self.piranha_led.set_brightness(percent)
        except Exception as e:
            if self.enable_debug:
                print('led set error:', e)

    def _set_buzzer_freq(self, freq_hz):
        """
        统一调用 Buzzer 实例播放音符或静音。
        - 若 freq_hz 为 0 或等价 False：调用 play_tone(0,1) 作为静音退路
        - 否则调用 play_tone(freq, 180)（duration 180ms，与任务周期 200ms 接近）
        捕获异常并在 enable_debug=True 时打印错误信息。
        注意：这里假定 play_tone 是非阻塞或内部处理不会长时间阻塞 tick()。
        """
        if self.buzzer is None:
            return
        try:
            if not freq_hz or freq_hz == 0:
                self.buzzer.play_tone(0, 1)
            else:
                self.buzzer.play_tone(freq_hz, 120)
        except Exception as e:
            if self.enable_debug:
                print('buzzer set error:', e)

    def tick(self):
        """
        调度器每 200ms 调用一次：
        1) 从 rcwl 读取原始距离（可以为 None）
        2) 如果 raw 有效且与 last_valid 差值 <= 100，则加入三点缓冲并更新 last_valid
           否则丢弃该次读数（认为是异常跳变或瞬时错误）
        3) 对缓冲做三点均值滤波（若缓冲为空则用 last_valid）
        4) 根据滤波值计算 LED 占空比与音符 -> 频率
        5) 调用硬件适配层输出 LED 与蜂鸣器
        6) 根据 enable_debug 打印调试信息
        """
        self.raw = None
        try:
            if self.rcwl is None:
                self.raw = None
            else:
                self.raw = self.rcwl.read_distance()
        except Exception as e:
            if self.enable_debug:
                print('sensor read error:', e)
            self.raw = None

        if self.raw is None:
            if self.enable_debug:
                print('sensor read: None (ignore)')
        else:
            # 初始状态或上次有效值为None时直接接受
            if self._last_valid is None or abs(self.raw - self._last_valid) <= 100:
                self._buf.append(self.raw)
                self._last_valid = self.raw
                if self.enable_debug:
                    print('sensor accepted ( delta < 100):', self.raw, 'prev_valid:', self._last_valid)
            else:
                # 差值 > 100 被视为异常跳变并忽略（最小改动：记录/打印）
                self._outlier_cnt += 1
                if self.enable_debug:
                    print('sensor outlier (delta>100) ignored:', self.raw, 'last_valid:', self._last_valid)

        if len(self._buf) == 0:
            filt = self._last_valid
        else:
            filt = sum(self._buf) / len(self._buf)

        duty = self._compute_led_duty(filt)
        note = self._choose_note(filt)
        freq = 0
        if note != 'OFF':
            freq = NOTE_FREQS.get(note, 0)

        # 输出
        self._set_led_duty(duty)
        self._set_buzzer_freq(freq)
        self._out_duty = duty

        if self.enable_debug:
            print('raw:', self.raw, 'filt:', filt, 'led duty:', duty, 'buzzer:', freq, note)

    def clear_filter(self):
        """
        清空滤波缓冲与上次有效值。
        可在暂停时调用，避免恢复后立刻使用旧缓冲导致突变。
        """
        try:
            while self._buf:
                self._buf.popleft()
            self._last_valid = None
        except Exception:
            pass

    def immediate_off(self):
        """
        立即熄灯并静音（供按键切换时立即生效），并清空滤波缓冲。
        该接口在 toggle 回调中会被调用以保证切换的即时性。
        """
        try:
            self._set_led_duty(0)
            self._set_buzzer_freq(0)
            self.clear_filter()
        except Exception:
            pass

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================