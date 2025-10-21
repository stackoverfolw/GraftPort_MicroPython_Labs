# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/10 下午6:30
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : PIR 红外传感器任务逻辑：检测人体后驱动泡泡枪机芯转动 5 秒，锁定 3 秒防止重复触发（PWM驱动版）
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import time
# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

class SensorMotorTask:
    """
    任务说明：
        每次调度器调用 tick() 时：
            1. 读取 PIR 红外传感器电平；
            2. 检测到高电平（运动）后加 200ms 消抖；
            3. 若仍为高电平 -> 启动电机（PWM输出100%占空比）；
            4. 电机运行 5 秒后停止（占空比设为 0%）；
            5. 进入锁定期 3 秒，在此期间忽略新的触发；
            6. 若 enable_debug=True，则打印状态信息。

    构造参数：
        pir         : PIRSensor 实例，提供 is_motion_detected()
        motor1, motor2 : OptoMosSimple 实例（PWM控制），具有 set_percent(percent) 方法
        enable_debug: 是否启用调试输出
    """

    def __init__(self, pir, motor1, motor2=None, enable_debug=False):
        self.pir = pir
        self.motor1 = motor1
        self.motor2 = motor2
        self.enable_debug = enable_debug

        # 内部状态变量
        self._state = "IDLE"        # 状态机：IDLE / RUNNING / LOCKED
        self._run_start = 0         # 电机启动时间戳
        self._lock_start = 0        # 锁定期开始时间戳
        self._debounce_ts = 0       # 消抖时间戳

    # ======================================== 内部方法 ========================================

    def _motor_on(self):
        """开启电机（PWM输出100%占空比）"""
        try:
            self.motor1.set_percent(100.0)
            if self.motor2:
                self.motor2.set_percent(100.0)
            if self.enable_debug:
                print("[MOTOR] ON (100%)")
        except Exception as e:
            if self.enable_debug:
                print("[ERROR] motor_on:", e)

    def _motor_off(self):
        """关闭电机（PWM占空比设为0%）"""
        try:
            self.motor1.set_percent(0.0)
            if self.motor2:
                self.motor2.set_percent(0.0)
            if self.enable_debug:
                print("[MOTOR] OFF (0%)")
        except Exception as e:
            if self.enable_debug:
                print("[ERROR] motor_off:", e)


    def immediate_off(self):
        """
        立即关闭电机输出（用于暂停任务或紧急停止）。
        不修改状态机，仅强制停止 PWM 输出。
        """
        try:
            self.motor1.set_percent(0.0)
            if self.motor2:
                self.motor2.set_percent(0.0)
            if self.enable_debug:
                print("[MOTOR] IMMEDIATE OFF")
        except Exception as e:
            if self.enable_debug:
                print("[ERROR] immediate_off:", e)
    # ======================================== 主任务逻辑 =======================================

    def tick(self):
        """
        每 100~200ms 调用一次。
        状态机逻辑：
            IDLE -> 检测到运动 -> RUNNING
            RUNNING -> 运行 5 秒 -> LOCKED
            LOCKED -> 3 秒后恢复 IDLE
        """
        now = time.ticks_ms()

        # ---- 状态：IDLE（等待触发） ----
        if self._state == "IDLE":
            try:
                motion = self.pir.is_motion_detected()
                print(self.pir.pin.value())
            except Exception as e:
                if self.enable_debug:
                    print("[ERROR] PIR read:", e)
                motion = False

            if motion is True:
                # 第一次检测到高电平，记录时间等待 200ms 消抖
                if self._debounce_ts == 0:
                    self._debounce_ts = now
                    if self.enable_debug:
                        print("[PIR] motion detected, debounce start")
                else:
                    # 检查是否超过 200ms 且仍然为高电平
                    if time.ticks_diff(now, self._debounce_ts) >= 200:
                        if self.enable_debug:
                            print("[PIR] confirmed -> start motor")
                        self._motor_on()
                        self._run_start = now
                        self._state = "RUNNING"
                        self._debounce_ts = 0
            else:
                # 无检测信号则重置消抖计时
                self._debounce_ts = 0

        # ---- 状态：RUNNING（电机运行中） ----
        elif self._state == "RUNNING":
            if time.ticks_diff(now, self._run_start) >= 10000:  # 5 秒到期
                self._motor_off()
                self._lock_start = now
                self._state = "LOCKED"
                if self.enable_debug:
                    print("[STATE] -> LOCKED (cooldown 3s)")

        # ---- 状态：LOCKED（冷却锁定期） ----
        elif self._state == "LOCKED":
            if time.ticks_diff(now, self._lock_start) >= 3000:  # 3 秒锁定结束
                self._state = "IDLE"
                if self.enable_debug:
                    print("[STATE] -> IDLE")

        # ---- 调试信息 ----
        if self.enable_debug:
            print("[DEBUG]", self._state)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
