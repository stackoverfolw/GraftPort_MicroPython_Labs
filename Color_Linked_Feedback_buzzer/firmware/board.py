# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/9 下午9:50   
# @Author  : 李清水            
# @File    : board.py       
# @Description : 多板支持的板级引脚与外设映射，提供结构化接口访问
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# ======================================== 全局变量 ============================================

# 接口类型常量
I2C0 = 0
I2C1 = 1
UART0 = 0
UART1 = 1
DIO0 = 0
DIO1 = 1
ADC0 = 0
ADC1 = 1
ADC2 = 2

BOARDS = {
    # GraftPort-RP2040 开发板配置
    "graftport_rp2040": {
        "NAME": "GraftPort-RP2040",

        # 固定硬件连接（不可更改）
        "FIXED_PINS": {
            "UART0_TX": 0,  # 板载USB转TTL的UART0_TX
            "UART0_RX": 1,  # 板载USB转TTL的UART0_RX
            "LED": 25,  # 板载LED
            "BUTTON": 18,  # 用户按键
            "WATCHDOG_WDI": 22,  # 看门狗WDG_WDI
        },

        # SD卡SPI接口（固定）
        "SD_SPI": {
            "SPI_ID": 1,
            "SCLK": 10,
            "MOSI": 11,
            "MISO": 12,
            "CS": 13,
        },

        # 接口映射
        "INTERFACES": {
            # I2C接口
            "I2C": {
                I2C0: {"SDA": 4, "SCL": 5},
                I2C1: {"SDA": 2, "SCL": 3},
            },

            # UART接口
            "UART": {
                UART0: {"TX": 16, "RX": 17},
                UART1: {"TX": 8, "RX": 9},
            },

            # 数字IO接口
            "DIO": {
                DIO0: (6, 7),  # DIO0: (DIO0_PIN, DIO1_PIN)
                DIO1: (14, 15),  # DIO1: (DIO2_PIN, DIO3_PIN)
            },

            # ADC接口
            "ADC": {
                ADC0: (26, 19),  # ADC0: (ADC0_PIN, DIO6_PIN)
                ADC1: (27, 20),  # ADC1: (ADC1_PIN, DIO5_PIN)
                ADC2: (28, 21),  # ADC2: (ADC2_PIN, DIO4_PIN)
            },
        },

        # 默认配置
        "DEFAULTS": {
            "I2C_FREQ": 400000,
            "UART_BAUD": 115200,
            "LED_ACTIVE_LOW": False,
            "HAS_SD": True,
        }
    },

    # 其他开发板配置可以继续添加...
}

# 默认激活的开发板
ACTIVE_BOARD = "graftport_rp2040"

# 导出当前板的配置对象
_config = BOARDS.get(ACTIVE_BOARD, {})

# ======================================== 功能函数 ============================================

def validate_board(name: str) -> bool:
    """
    校验给定的板名是否存在于 BOARDS 中（布尔返回）。

    Args:
        name (str): 要校验的板名称。

    Returns:
        bool: 返回 True 表示存在，False 表示不存在。

    Raises:
        None

    Notes：
        仅在内存中的 BOARDS 字典中查找，不进行 I/O 操作。

    ==========================================

    Validate whether the given board name exists in BOARDS.

    Args:
        name (str): Board name to validate.

    Returns:
        bool: True if exists, False otherwise.

    Raises:
        None

    Notes：
        Only checks the in-memory BOARDS mapping; no I/O.
    """
    return name in BOARDS

def set_active_board(name: str) -> bool:
    """
    设置当前活动板（运行时可调用），并把对应配置赋给 _config。

    Args:
        name (str): 要设置为活动的板名称。

    Returns:
        bool: 返回 True 表示设置成功，False 表示失败（例如 name 不存在）。

    Raises:
        None

    Notes：
        函数不抛出异常以保持运行时安全，遇到无效 name 时返回 False。

    ==========================================

    Set the active board at runtime and update the _config.

    Args:
        name (str): Board name to activate.

    Returns:
        bool: True if successfully set, False if failed (e.g., name not found).

    Raises:
        None

    Notes：
        This function does not raise; it returns False for invalid names.
    """
    global ACTIVE_BOARD, _config
    if not validate_board(name):
        return False
    ACTIVE_BOARD = name
    _config = BOARDS[name]
    return True

def get_config() -> dict:
    """
    返回当前激活板的配置字典。

    Args:
        无参数

    Returns:
        dict: 当前激活板的完整配置字典（若未设置可能为空字典或默认配置）。

    Raises:
        None

    Notes：
        返回的是 _config 的引用（若需防止外部修改可返回副本）。

    ==========================================

    Return the configuration dictionary of the currently active board.

    Args:
        None

    Returns:
        dict: Configuration dict for the active board (may be empty if unset).

    Raises:
        None

    Notes：
        Returns the _config reference; return a copy if mutation safety is required.
    """
    return _config

def list_boards() -> list:
    """
    返回可用板子的名称列表。

    Args:
        无参数

    Returns:
        list: 可用板子的名称列表。

    Raises:
        None

    Notes：
        列表顺序与 BOARDS 的键顺序有关（Python 3.7+ 保持插入顺序）。

    ==========================================

    Return the list of available board names.

    Args:
        None

    Returns:
        list: List of available board names.

    Raises:
        None

    Notes：
        The order follows BOARDS key insertion order (Python 3.7+).
    """
    return list(BOARDS.keys())

def get_fixed_pin(pin_name: str):
    """
    获取固定用途的引脚编号（若不存在返回 None）。

    Args:
        pin_name (str): 固定用途引脚的逻辑名称（如 "LED"、"BUZZER"）。

    Returns:
        int or None: 引脚号（整数）或 None 表示未配置。

    Raises:
        None

    Notes：
        返回值直接来自 _config["FIXED_PINS"]，未做额外转换。

    ==========================================

    Get the pin number for a named fixed-purpose pin (or None if not configured).

    Args:
        pin_name (str): Logical name for the fixed pin (e.g., "LED", "BUZZER").

    Returns:
        int or None: Pin number or None if not configured.

    Raises:
        None

    Notes：
        The value is returned directly from _config["FIXED_PINS"] without conversion.
    """
    return _config.get("FIXED_PINS", {}).get(pin_name)

def get_sd_spi_config() -> dict:
    """
    获取 SD 卡 的 SPI 配置（字典形式）。

    Args:
        无参数

    Returns:
        dict: SD 卡 SPI 配置字典（可能为空字典）。

    Raises:
        None

    Notes：
        典型返回可能包含 MOSI/MISO/SCK/CS 引脚号等信息，结构由 BOARDS 定义。

    ==========================================

    Get the SD card SPI configuration as a dict.

    Args:
        None

    Returns:
        dict: SD SPI configuration dict (may be empty).

    Raises:
        None

    Notes：
        Typical entries may include MOSI/MISO/SCK/CS; structure defined by BOARDS.
    """
    return _config.get("SD_SPI", {})

def get_i2c_pins(i2c_id: str):
    """
    获取指定 I2C 接口的 SDA 和 SCL 引脚编号；找不到时返回 (None, None)。

    Args:
        i2c_id (str): I2C 接口标识（例如 "0"、"1" 或逻辑名）。

    Returns:
        tuple: (SDA_pin, SCL_pin) 或 (None, None)。

    Raises:
        None

    Notes：
        返回值直接来自 _config["INTERFACES"]["I2C"] 的子字典。

    ==========================================

    Get the SDA and SCL pin numbers for the specified I2C interface.

    Args:
        i2c_id (str): I2C interface identifier (e.g., "0", "1", or logical name).

    Returns:
        tuple: (SDA_pin, SCL_pin) or (None, None).

    Raises:
        None

    Notes：
        Values are read from _config["INTERFACES"]["I2C"].
    """
    i2c_config = _config.get("INTERFACES", {}).get("I2C", {})
    if i2c_id in i2c_config:
        cfg = i2c_config[i2c_id]
        return cfg.get("SDA"), cfg.get("SCL")
    return None, None

def get_uart_pins(uart_id: str):
    """
    获取指定 UART 接口的 TX 和 RX 引脚编号；找不到时返回 (None, None)。

    Args:
        uart_id (str): UART 接口标识（例如 "0"、"1" 或逻辑名）。

    Returns:
        tuple: (TX_pin, RX_pin) 或 (None, None)。

    Raises:
        None

    Notes：
        返回值来自 _config["INTERFACES"]["UART"] 的配置结构。

    ==========================================

    Get the TX and RX pin numbers for the specified UART interface.

    Args:
        uart_id (str): UART interface identifier (e.g., "0", "1", or logical name).

    Returns:
        tuple: (TX_pin, RX_pin) or (None, None).

    Raises:
        None

    Notes：
        Values are read from _config["INTERFACES"]["UART"].
    """
    uart_config = _config.get("INTERFACES", {}).get("UART", {})
    if uart_id in uart_config:
        cfg = uart_config[uart_id]
        return cfg.get("TX"), cfg.get("RX")
    return None, None

def get_dio_pins(dio_id: str):
    """
    获取指定数字 IO 接口的引脚编号配置；找不到返回 None。

    Args:
        dio_id (str): 数字 IO 接口标识。

    Returns:
        dict or None: 对应的引脚配置字典或 None。

    Raises:
        None

    Notes：
        该函数不对字典格式做严格校验，调用方应按需验证字段。

    ==========================================

    Get the pin configuration dict for the specified digital I/O interface.

    Args:
        dio_id (str): Digital I/O interface identifier.

    Returns:
        dict or None: The pin configuration dict or None.

    Raises:
        None

    Notes：
        No strict validation performed; caller should verify fields as needed.
    """
    dio_config = _config.get("INTERFACES", {}).get("DIO", {})
    if dio_id in dio_config:
        return dio_config[dio_id]
    return None

def get_adc_pins(adc_id: str):
    """
    获取指定 ADC 接口的引脚编号配置；找不到返回 None。

    Args:
        adc_id (str): ADC 接口标识。

    Returns:
        dict or None: 对应的 ADC 引脚配置字典或 None。

    Raises:
        None

    Notes：
        返回格式与 BOARDS 中的 "ADC" 配置项一致（通常为通道到引脚的映射）。

    ==========================================

    Get the pin configuration dict for the specified ADC interface.

    Args:
        adc_id (str): ADC interface identifier.

    Returns:
        dict or None: The ADC pin configuration dict or None.

    Raises:
        None

    Notes：
        Format follows BOARDS["INTERFACES"]["ADC"] structure.
    """
    adc_config = _config.get("INTERFACES", {}).get("ADC", {})
    if adc_id in adc_config:
        return adc_config[adc_id]
    return None

def get_default_config(config_name: str):
    """
    获取当前激活板的默认配置值（DEFAULTS 中的项），未找到返回 None。

    Args:
        config_name (str): 配置项名称。

    Returns:
        any: 配置值或 None（若未定义）。

    Raises:
        None

    Notes：
        DEFAULTS 子字典用于存放与板相关的默认运行时参数。

    ==========================================

    Get a default configuration value from the active board's DEFAULTS.

    Args:
        config_name (str): Name of the configuration entry.

    Returns:
        any: The configuration value or None if not defined.

    Raises:
        None

    Notes：
        DEFAULTS is intended for board-specific runtime defaults.
    """
    return _config.get("DEFAULTS", {}).get(config_name)

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 确保_config与ACTIVE_BOARD一致
if ACTIVE_BOARD in BOARDS:
    _config = BOARDS[ACTIVE_BOARD]
else:
    # 如果ACTIVE_BOARD不合法，退回第一个可用板
    try:
        first_board = next(iter(BOARDS))
        ACTIVE_BOARD = first_board
        _config = BOARDS[first_board]
    except StopIteration:
        # BOARDS为空时，保持空配置
        _config = {}

# ========================================  主程序  ===========================================