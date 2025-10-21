# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/18 下午7:30
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : NFC门禁控制
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 ============================================

import time
from firmware.drivers.bus_step_motor_driver import BusStepMotor  # 仅用于类型提示和常量引用,使用thonny删掉firmware.

# ======================================== 核心参数配置 ============================================
# 电机控制参数（与BusStepMotor驱动匹配）
MOTOR_ID = 1  # 电机编号（1开始，与驱动一致）
DRIVER_MODE = BusStepMotor.DRIVER_MODE_HALF_STEP  # 半步驱动模式
TARGET_ANGLE = 90  # 目标转动角度
MOTOR_STEPS_PER_REV = 64  # 电机固有步数（全步64*64=4096）
GEAR_RATIO = 64  # 减速比1:64
MOTOR_SPEED = 150  # 电机速度（步/秒）

# 门禁逻辑参数
DOOR_HOLD_SECONDS = 5  # 门保持时间
SCAN_INTERVAL_MS = 300  # NFC扫描间隔
REPEAT_IGNORE_SECONDS = 5  # 重复刷卡忽略时间

# 计算90度步数
STEPS_PER_360 = MOTOR_STEPS_PER_REV * GEAR_RATIO
STEPS_FOR_90 = int(STEPS_PER_360 / 4)


# ======================================== 自定义类 ============================================
class NFCDoorTask:
    def __init__(self, pn532=None, motor=None, oled=None,
                 authorized_uids=None, enable_debug: bool = False):
        # 外部传入硬件实例（无初始化）
        self.pn532 = pn532  # NFC模块实例（外部初始化）
        self.motor = motor  # BusStepMotor实例（外部初始化）
        self.oled = oled  # OLED实例（外部初始化，可选）
        self.enable_debug = enable_debug

        # 授权UID处理
        self.authorized_uids = self._normalize_uids(authorized_uids) if authorized_uids else []

        # 状态变量（与原有风格一致）
        self.last_uid = None
        self.last_trigger_time = 0
        self.door_status = "closed"
        self.last_scan_time = 0
        self.is_processing = False  # 防止并发处理
        self.hold_start_time = 0  # 门保持计时

    # -------------------------- 辅助方法 --------------------------
    def _normalize_uids(self, uids):
        """统一UID格式（与原有处理逻辑一致）"""
        normalized = []
        for uid in uids:
            if isinstance(uid[0], str):
                normalized_uid = [int(byte, 16) for byte in uid]
            else:
                normalized_uid = uid
            normalized.append(normalized_uid)
        return normalized

    # -------------------------- NFC卡读取与验证 --------------------------
    def _read_card_uid(self):
        """读取NFC UID（保持原有方法名和逻辑）"""
        if self.pn532 is None:
            return None

        try:
            uid_bytes = self.pn532.read_passive_target()
            if uid_bytes:
                if self.enable_debug:
                    print(f"Card detected: {uid_bytes}")
                uid_int = [int(byte) & 0xFF for byte in uid_bytes]
                if self.enable_debug:
                    print(f"Converted UID: {[hex(b) for b in uid_int]}")
                return uid_int
            return None
        except Exception as e:
            if self.enable_debug:
                print(f"Card reading error: {str(e)}")
            return None

    def _is_authorized(self, uid):
        """验证UID授权（保持原有方法名）"""
        if not uid:
            return False

        if self.enable_debug:
            print(f"Verifying UID: {uid}")
            print(f"Authorized UID list: {self.authorized_uids}")

        return uid in self.authorized_uids

    # -------------------------- 电机控制（适配BusStepMotor） --------------------------
    def _rotate_exact_angle(self, direction):
        """转动指定角度（调用BusStepMotor方法）"""
        if self.motor is None:
            return False

        try:
            # 调用BusStepMotor的定步运动方法
            self.motor.start_step_motion(
                motor_id=MOTOR_ID,
                direction=direction,
                driver_mode=DRIVER_MODE,
                speed=MOTOR_SPEED,
                steps=STEPS_FOR_90
            )

            # 等待转动完成
            wait_time = (STEPS_FOR_90 / MOTOR_SPEED) + 0.5
            time.sleep(wait_time)

            # 停止电机（双重保险）
            self.motor.stop_step_motion(MOTOR_ID)
            if self.enable_debug:
                print(f"{TARGET_ANGLE}° rotation completed")
            return True

        except Exception as e:
            if self.enable_debug:
                print(f"Motor rotation error: {str(e)}")
            self.motor.stop_step_motion(MOTOR_ID)
            return False

    # -------------------------- 门状态控制 --------------------------
    def _open_door(self):
        """开门逻辑（保持原有方法名）"""
        if self.door_status == "open":
            return True

        if self.enable_debug:
            print("Executing door open (90 degrees)...")
        success = self._rotate_exact_angle(BusStepMotor.FORWARD)
        if success:
            self.door_status = "open"
            self.hold_start_time = time.time()  # 记录开门时间
        return success

    def close_door(self):
        """关门逻辑（保持原有方法名）"""
        if self.door_status == "closed":
            return True

        if self.enable_debug:
            print("Executing door close (90 degrees)...")
        success = self._rotate_exact_angle(BusStepMotor.BACKWARD)
        if success:
            self.door_status = "closed"
            self.last_uid = None  # 重置缓存
        return success

    # -------------------------- OLED显示 --------------------------
    def _update_display(self, message=None):
        """OLED显示（保持原有方法名和逻辑）"""
        if self.oled is None:
            return

        try:
            self.oled.fill(0)
            self.oled.text("NFC Door Control", 0, 0)
            self.oled.text(f"Status: {self.door_status}", 0, 16)  # 状态值与变量一致
            if message:
                self.oled.text(message, 0, 32)
            else:
                self.oled.text("Scan card...", 0, 32)
            self.oled.show()
        except Exception as e:
            if self.enable_debug:
                print(f"OLED error: {str(e)}")

                # 核心任务逻辑使用tick()方法

    def tick(self):
        """主调度方法（保持原有入口，循环调用）"""
        current_time = time.ticks_ms()

        # 控制扫描频率
        if time.ticks_diff(current_time, self.last_scan_time) < SCAN_INTERVAL_MS:
            return
        self.last_scan_time = current_time

        # 处理中则跳过
        if self.is_processing:
            if self.enable_debug:
                print("Processing in progress, skipping scan")
            return

        try:
            # 门保持逻辑（开门后保持指定时间）
            if self.door_status == "open":
                if time.time() - self.hold_start_time >= DOOR_HOLD_SECONDS:
                    self.close_door()
                    self._update_display("Closed")
                return

            # 读取NFC卡片
            uid = self._read_card_uid()

            if uid:
                current_sec = time.time()
                # 忽略重复刷卡
                is_repeat = (self.last_uid == uid) and \
                            (current_sec - self.last_trigger_time < REPEAT_IGNORE_SECONDS)

                if not is_repeat:
                    self.is_processing = True
                    self.last_uid = uid

                    # 验证授权并开门
                    if self._is_authorized(uid):
                        if self._open_door():
                            self._update_display("Opened")
                            self.last_trigger_time = current_sec
                    else:
                        self._update_display("Unauthorized")
                        if self.enable_debug:
                            print("Unauthorized card")
                        time.sleep(1)

                    self.is_processing = False
                else:
                    if self.enable_debug:
                        print(f"Ignoring repeated card (within {REPEAT_IGNORE_SECONDS} seconds)")
            else:
                self._update_display()

        except Exception as e:
            self.is_processing = False
            if self.enable_debug:
                print(f"Task error: {str(e)}")
            self._update_display("Error")
# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
