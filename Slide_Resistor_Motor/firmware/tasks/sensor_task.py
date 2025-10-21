# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/10 下午4:32   
# @Author  : 缪贵成
# @File    : sensor_task.py       
# @Description : 读取滑动变阻器的值映射到电机驱动模块pwm,从而实现滑动变阻器控制直流电机转速操作，oled显示转速和pwm
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# ======================================== 自定义类 ============================================

class SensorPotMotorTask:
    """
    任务：每 100ms 调度一次
    构造参数：
        adc: ADC 实例 (machine.ADC)
        motor: 电机驱动实例 (需提供 set_speed(percent) / stop())
        oled: OLED 显示实例 (需提供 fill()/text()/show())
        enable_debug: 是否开启调试信息打印
    """

    def __init__(self, speed_exp: float = 3.0, poten=None, motor=None, oled=None, enable_debug: bool = False):
        self.poten = poten
        self.motor = motor
        self.oled = oled
        self.enable_debug = enable_debug
        self.last_duty = 0   # 上次占空比
        self._speed_exp = float(speed_exp)

    def _duty_to_speed(self, duty: int) -> int:
        """
        将占空比 (0..100) 非线性映射为电机速度绝对值，并限制在 1900..4095。

        采用幂次曲线：norm = (duty/100) ** exp
        speed = MIN + norm * (MAX - MIN)

        更大的 exp -> 在低 duty 时速度更接近 MIN，直到高 duty 时快速上升（更“剧烈”）
        """
        min_speed = 1900
        max_speed = 4095

        # 边界快速处理
        if duty <= 0:
            return min_speed
        if duty >= 100:
            return max_speed

        # 归一化并做幂次映射
        norm = (duty / 100.0) ** self._speed_exp
        speed = min_speed + norm * (max_speed - min_speed)

        # 裁剪并取整
        if speed < min_speed:
            speed = min_speed
        elif speed > max_speed:
            speed = max_speed

        return int(round(speed))
    def tick(self):
        """
        每 100ms 调用一次：
        1. 从 ADC 读取电位器值 (0~65535 或 0~4095)
        2. 映射为 0~100% 占空比
        3. 更新电机 PWM
        4. OLED 显示信息
        5. 异常时电机停转
        """
        # 参数检查
        if self.poten is None or self.motor is None or self.oled is None:
            if self.enable_debug:
                print("[WARNING] Missing hardware instance, skip tick.")
            return

        try:
            # 读取 ADC 归一化值
            duty = (self.poten.read_ratio()*100)
            # 转换为电机速度
            speed = self._duty_to_speed(duty)

            # 控制电机
            self.motor.set_motor_speed(1, speed, 0)
            self.last_duty = duty

            # OLED 显示
            self.oled.fill(0)
            self.oled.text(f"Motor Speed: {speed}%", 0, 0)
            self.oled.text(f"PWM Duty: {duty}%", 0, 16)
            self.oled.show()

            if self.enable_debug:
                print(f"[INFO]Duty={duty}%")

        except Exception as e:
            # 异常时停电机
            try:
                self.motor.stop_motor()
            except Exception:
                pass
            if self.enable_debug:
                print("[ERROR] MotorControlTask tick failed:", e)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================