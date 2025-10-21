# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/9/10 下午4:32
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : 编码器控制步进电机，每格编码器转动对应50步电机运动
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import time

# ======================================== 全局变量 ============================================

# 核心参数调整：每格编码器对应50步电机运动
MOTOR_SPEED = 400  # 提高速度，使50步运动更明显
ENCODER_TO_MOTOR_RATIO = 50  # 编码器每格对应电机步数
TICK_INTERVAL_MS = 50  # 适中的调度间隔
MIN_ENCODER_DELTA = 1  # 编码器最小变化量（1格）

# ======================================== 自定义类 ============================================

class StepperEncoderTask:
    """
    编码器控制步进电机任务类
    特性：编码器每转动1格，电机对应转动50步，运动更明显
    """

    def __init__(self, encoder=None, motor=None, oled=None,
                 motor_id: int = 1, enable_debug: bool = False,
                 max_steps: int = 5000, speed: int = MOTOR_SPEED):
        self.encoder = encoder
        self.motor = motor
        self.oled = oled
        self.motor_id = motor_id
        self.enable_debug = enable_debug

        # 步数与状态变量
        self.total_steps = 0  # 电机总步数
        self.max_steps = max_steps  # 最大允许步数
        self._last_enc_count = None  # 上一次编码器计数
        self._last_dir = "CW"  # 上一次方向
        self._running = False  # 电机运行状态
        self._speed = speed  # 电机速度

        # 驱动模式常量
        self.DIR_FORWARD = getattr(self.motor, "FORWARD", 0)
        self.DIR_BACKWARD = getattr(self.motor, "BACKWARD", 1)
        self.DRIVER_MODE = getattr(self.motor, "DRIVER_MODE_HALF_STEP", 2)

    # -------------------------- 编码器读取 --------------------------
    def _read_encoder_delta(self) -> int:
        """读取编码器变化量，返回变化格数"""
        if self.encoder is None:
            return 0

        try:
            current = self.encoder.get_rotation_count()
        except Exception:
            current = getattr(self.encoder, "rotation_count", 0)

        if self._last_enc_count is None:
            self._last_enc_count = current
            return 0

        delta = current - self._last_enc_count
        self._last_enc_count = current
        return int(delta)

    # -------------------------- 电机控制 --------------------------
    def _run_step(self, step_count: int, direction: int):
        """执行指定步数的电机运动"""
        if self.motor is None or step_count <= 0 or self._running:
            return False

        try:
            self.motor.start_step_motion(
                self.motor_id,
                direction,
                self.DRIVER_MODE,
                self._speed,
                step_count
            )
            self._running = True
            if self.enable_debug:
                print(f"[MOTOR] steps={step_count}, dir={direction}, speed={self._speed}")

            # 等待当前批次完成
            while self._running:
                # 检查电机是否仍在运行（简单的轮询方式）
                time.sleep_ms(10)
                # 对于定步运动，可通过步数判断是否完成
                # 这里简化处理，假设电机能按指令完成所有步数
                self._running = False

            return True
        except Exception as e:
            self._running = False
            if self.enable_debug:
                print(f"[ERROR] motion failed: {e}")
            return False

    def _stop_motor(self):
        """立即停止电机"""
        try:
            if hasattr(self.motor, "stop_step_motion"):
                self.motor.stop_step_motion(self.motor_id)
            elif hasattr(self.motor, "stop"):
                self.motor.stop(self.motor_id)
        except Exception:
            pass
        self._running = False

    # -------------------------- 周期任务（核心逻辑） --------------------------
    def tick(self):
        """
        周期性任务处理函数
        每转动1格编码器，电机对应转动50步
        """
        if self.encoder is None or self.motor is None:
            return

        try:
            # 1. 读取编码器变化
            delta = self._read_encoder_delta()
            if abs(delta) >= MIN_ENCODER_DELTA:
                # 确定方向
                direction = self.DIR_FORWARD if delta > 0 else self.DIR_BACKWARD
                self._last_dir = "CW" if delta > 0 else "CCW"

                # 计算电机需要转动的步数：编码器变化量 × 比例系数
                motor_steps = abs(delta) * ENCODER_TO_MOTOR_RATIO

                # 更新总步数并限制范围
                self.total_steps += motor_steps if direction == self.DIR_FORWARD else -motor_steps
                self.total_steps = max(0, min(self.total_steps, self.max_steps))

                # 执行电机运动
                self._run_step(motor_steps, direction)

                if self.enable_debug:
                    print(f"[INFO] Encoder delta={delta}, Motor steps={motor_steps}, Dir={self._last_dir}")

            # 2. OLED显示
            if self.oled is not None:
                try:
                    self.oled.fill(0)
                    self.oled.text(f"Dir: {self._last_dir}", 0, 0)
                    self.oled.text(f"Total: {self.total_steps:3d}", 0, 16)
                    self.oled.text(f"Ratio: 1:{ENCODER_TO_MOTOR_RATIO}", 0, 32)
                    self.oled.text(f"Speed: {self._speed}", 0, 48)
                    self.oled.show()
                except Exception as e:
                    if self.enable_debug:
                        print(f"[ERROR] OLED update failed: {e}")

        except Exception as e:
            if self.enable_debug:
                print(f"[ERROR] tick failed: {e}")
            self._stop_motor()
# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================