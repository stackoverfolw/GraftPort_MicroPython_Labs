# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/08/19 12:30
# @Author  : 零高幸
# @File    : piranha_led.py
# @Description : 控制共阳极或共阴极LED的驱动模块，v1.1.0 版本增加了对 PWM 的支持。
# @License : CC BY-NC 4.0

__version__ = "1.1.0"
__author__ = "零高幸"
__license__ = "CC BY-NC 4.0"
__platform__ = "MicroPython v1.23+"

# ======================================== 导入相关模块 =========================================

# 标准库
from machine import Pin, PWM
# 导入MicroPython相关模块
from micropython import const

# ======================================== 全局变量 ============================================

# LED 极性常量
POLARITY_CATHODE = const(0)  # 共阴极：高电平亮
POLARITY_ANODE   = const(1)  # 共阳极：低电平亮

# ======================================== 功能函数 ============================================

def _calculate_output(desired_on: bool, polarity: int) -> int:
    """
    根据LED类型和期望状态，计算GPIO应输出的电平。

    Args:
        desired_on (bool): True表示希望LED点亮。
        polarity (int): LED类型，POLARITY_CATHODE 或 POLARITY_ANODE。

    Returns:
        int: 0表示LOW，1表示HIGH。

    Raises:
        ValueError: 如果polarity非法。

    ==========================================
    Calculate GPIO level based on LED type and desired state.

    Args:
        desired_on (bool): True if LED should be on.
        polarity (int): LED type, POLARITY_CATHODE or POLARITY_ANODE.

    Returns:
        int: 0 for LOW, 1 for HIGH.

    Raises:
        ValueError: If polarity is invalid.
    """
    if polarity == POLARITY_CATHODE:
        return 1 if desired_on else 0
    elif polarity == POLARITY_ANODE:
        return 0 if desired_on else 1
    else:
        raise ValueError(f"Invalid polarity: {polarity}")

# ======================================== 自定义类 ============================================

class PiranhaLED:
    """
    LED 控制类，支持共阳极/共阴极连接方式及 PWM 调节亮度。

    该类封装了单个 LED 的控制逻辑，支持开/关、亮度调节、翻转状态
    和呼吸灯效果。通过 PWM 调节占空比，可实现从熄灭到最亮的平滑亮度控制，

    Attributes:
        _pin (Pin): LED 绑定的 GPIO 引脚实例。
        _pwm (PWM): 绑定的 PWM 实例，用于调节亮度。
        _polarity (int): LED 极性，POLARITY_CATHODE 或 POLARITY_ANODE。

    Methods:
        __init__(pin_number: int, polarity: int = POLARITY_CATHODE, freq: int = 1000) -> None:
            初始化 LED 对象。
        on() -> None:
            点亮 LED（100% 占空比）。
        off() -> None:
            熄灭 LED（0% 占空比）。
        toggle() -> None:
            翻转 LED 当前状态。
        is_on() -> bool:
            查询 LED 是否点亮。
        set_brightness(percent: int) -> None:
            设置 LED 亮度，占空比 0~100%。

    Notes:
        duty_u16=65535 表示 100% 占空比，0 表示 0% 占空比。
        共阳极 LED 的逻辑反转，即 duty 越大实际越暗。

    ==========================================

    LED control class supporting common anode/cathode and PWM brightness control.

    This class encapsulates control logic for a single LED, supporting
    on/off, brightness adjustment, state toggle, and breathing effect.
    By adjusting PWM duty cycle, smooth brightness control from off to
    maximum brightness is achieved, and PWM frequency can be dynamically
    adjusted to avoid flicker.

    Attributes:
        _pin (Pin): GPIO pin instance bound to the LED.
        _pwm (PWM): PWM instance for brightness control.
        _polarity (int): LED polarity, POLARITY_CATHODE or POLARITY_ANODE.

    Methods:
        __init__(pin_number: int, polarity: int = POLARITY_CATHODE, freq: int = 1000) -> None:
            Initialize LED object.
        on() -> None:
            Turn on LED (100% duty cycle).
        off() -> None:
            Turn off LED (0% duty cycle).
        toggle() -> None:
            Toggle current state of LED.
        is_on() -> bool:
            Check if LED is on.
        set_brightness(percent: int) -> None:
            Set LED brightness (0~100% duty cycle).

    Notes:
        duty_u16=65535 means 100% duty cycle, 0 means 0%.
        For common anode LEDs, logic is inverted (higher duty = dimmer).
    """

    def __init__(self, pin_number: int, polarity: int = POLARITY_CATHODE, freq: int = 1000):
        """
        初始化LED对象。

        Args:
            pin_number (int): GPIO引脚编号。
            polarity (int): LED类型，POLARITY_CATHODE（默认）或 POLARITY_ANODE。
            freq (int): PWM频率，默认1000Hz。

        ==========================================

        Initialize LED object.

        Args:
            pin_number (int): GPIO pin number.
            polarity (int): LED type, POLARITY_CATHODE (default) or POLARITY_ANODE.
            freq (int): PWM frequency, default 1000Hz.
        """
        # 参数校验，判断极性是否合法
        if polarity not in (POLARITY_CATHODE, POLARITY_ANODE):
            raise ValueError(f"Invalid polarity: {polarity}")

        # 参数校验，判断引脚号是否合法
        if pin_number < 0:
            raise ValueError(f"Invalid pin number: {pin_number}")

        self._pin = Pin(pin_number, Pin.OUT)
        # 初始化为0%亮度
        self._pwm = PWM(self._pin, freq=freq, duty_u16=0)
        self._polarity = polarity

    def on(self) -> None:
        """
        点亮LED（100%占空比）。

        ==========================================

        Turn on the LED (100% duty cycle).
        """
        duty = 65535 if self._polarity == POLARITY_CATHODE else 0
        self._pwm.duty_u16(duty)

    def off(self) -> None:
        """
        熄灭LED（0%占空比）。

        ==========================================

        Turn off the LED (0% duty cycle).
        """
        duty = 0 if self._polarity == POLARITY_CATHODE else 65535
        self._pwm.duty_u16(duty)

    def toggle(self) -> None:
        """
        翻转LED当前状态。

        ==========================================

        Toggle the current state of the LED.
        """
        if self.is_on():
            self.off()
        else:
            self.on()

    def is_on(self) -> bool:
        """
        查询LED是否处于点亮状态（基于PWM占空比判断）。

        Returns:
            bool: True表示点亮。

        ==========================================

        Check if the LED is on (based on PWM duty cycle).

        Returns:
            bool: True if LED is on.
        """
        duty = self._pwm.duty_u16()
        if self._polarity == POLARITY_CATHODE:
            return duty > 0
        else:
            return duty < 65535

    def set_brightness(self, percent: int) -> None:
        """
        设置LED亮度，占空比0~100%。

        Args:
            percent (int): 亮度百分比，0=熄灭，100=最亮。

        ==========================================

        Set LED brightness (0~100% duty cycle).

        Args:
            percent (int): Brightness percentage, 0=off, 100=full brightness.
        """
        if not 0 <= percent <= 100:
            raise ValueError("Brightness percent must be between 0 and 100")

        duty = int(65535 * (percent / 100))
        if self._polarity == POLARITY_CATHODE:
            self._pwm.duty_u16(duty)
        else:  # 共阳极逻辑反转
            self._pwm.duty_u16(65535 - duty)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================