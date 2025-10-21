# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10/20 上午9:00
# @Author  : 缪贵成
# @File    : sensor_task.py
# @Description : 智能绿植补水装置
# ======================================== 导入相关模块 =========================================
import time
import gc
from machine import Pin

# ======================================== 全局常量（注释中文，打印用英文） ======================
CHECK_INTERVAL_MS = 2000  # 主监测周期（毫秒）
BLINK_INTERVAL_MS = 500  # 报警闪烁周期（毫秒）
CALIBRATION_SAMPLES = 5  # 校准所需样本数量
CALIBRATION_BEEP_FREQ = 1000  # 校准提示音频率（Hz）
CALIBRATION_BEEP_DUR = 200  # 校准提示音时长（毫秒）
PRINT_INTERVAL = 2  # 样本进度打印间隔（每采集2个样本打印一次）
BUTTON_DEBOUNCE_MS = 50  # 按键防抖时间（避免误触发，毫秒）
LONG_PRESS_THRESHOLD = 2000  # 长按最短时长（2秒，用于确认校准）
SHORT_PRESS_MAX = 1000  # 短按最长时长（1秒，用于暂停/恢复任务）

# 系统状态常量（注释中文）
STATE_NORMAL = 0  # 正常监测状态
STATE_ALARM = 1  # 低湿度报警状态
STATE_CALIBRATE_DRY = 2  # 干燥环境校准状态（传感器放干燥空气）
STATE_CALIBRATE_WET = 3  # 湿润环境校准状态（传感器放水/湿土）


# ======================================== 自定义类（注释中文） ==================================
class PlantHealthMonitorTask:
    """
    绿植健康监测任务类
    核心功能：
    - 土壤湿度采集与计算
    - 干湿环境校准（长按按键确认）
    - OLED实时显示（校准进度/湿度/阈值）
    - 按键交互（短按暂停/恢复，长按确认校准）
    - 低湿度报警（LED闪烁+蜂鸣器提示）
    """

    def __init__(self, soil_sensor, potentiometer, oled, buzzer, led, button, enable_debug=False):
        # 硬件实例（从main.py传入，不内部重复初始化）
        self.soil_sensor = soil_sensor  # 土壤湿度传感器实例（需支持read_raw()/read_moisture()）
        self.potentiometer = potentiometer  # 滑动变阻器实例（用于调节报警阈值，需支持read_ratio()）
        self.oled = oled  # OLED显示屏实例（128x64分辨率，需支持fill()/text()/show()）
        self.buzzer = buzzer  # 蜂鸣器实例（用于提示音，需支持play_tone(freq, dur)）
        self.led = led  # LED指示灯实例（用于状态提示，需支持on()/off()）
        self.button = button  # 物理按键实例（用于用户交互，需支持value()读取状态）

        # 按键状态变量（新增，用于区分短按/长按）
        self.button_last_press = 0  # 上次按键按下的时间戳（毫秒）
        self.button_state = "released"  # 当前按键状态："pressed"（按下）/"released"（松开）
        self.task_paused = False  # 任务暂停标志：True=暂停，False=运行

        # 校准与系统状态变量
        self.calibration_completed = False  # 校准完成标志：True=已完成，False=未完成
        self.calibration_prompted = False  # 校准提示打印标志：避免重复输出说明
        self.samples_ready = False  # 校准样本就绪标志：True=样本足够（5个），False=不足
        self.system_state = STATE_CALIBRATE_DRY  # 初始状态：默认进入干燥校准
        self.current_moisture = 0.0  # 当前土壤湿度（百分比，保留1位小数）
        self.threshold = 30  # 湿度报警阈值（百分比，默认30%，可通过滑动变阻器调节）
        self.led_state = False  # LED闪烁状态：True=亮，False=灭
        self.last_check_time = 0  # 上次湿度检测的时间戳（毫秒）
        self.last_blink_time = 0  # 上次LED闪烁的时间戳（毫秒）
        self.calibration_samples = []  # 校准样本缓冲区（存储5个ADC原始值）
        self.enable_debug = enable_debug  # 调试日志开关：True=打印调试信息，False=不打印

        # 初始化完成提示（播放两声短提示音）
        self._init_complete()
        # 初始垃圾回收（释放内存，避免MicroPython内存溢出）
        gc.collect()

    # -------------------------- 传感器读取方法（注释中文，打印用英文） --------------------------
    def _read_soil_adc(self):
        """
        读取土壤湿度传感器的ADC原始值
        返回：ADC原始值（范围0-65535，值越大表示越干燥）
        异常：传感器读取失败时抛出Exception，含错误信息
        """
        try:
            return self.soil_sensor.read_raw()
        except Exception as e:
            raise Exception(f"Soil sensor read error: {e}")  # 打印英文错误信息

    def _read_potentiometer_ratio(self):
        """
        读取滑动变阻器的归一化比例值
        功能：将滑动变阻器的ADC值转换为0.0-1.0的比例，用于计算报警阈值
        返回：归一化比例（0.0=最小阻值，1.0=最大阻值）
        异常：滑动变阻器读取失败时抛出Exception，含错误信息
        """
        try:
            ratio = self.potentiometer.read_ratio()
            # 限制比例在0.0-1.0，避免阈值超出0-100%范围
            return max(0.0, min(1.0, ratio))
        except Exception as e:
            raise Exception(f"Potentiometer read error: {e}")  # 打印英文错误信息

    # -------------------------- 初始化完成提示（注释中文） --------------------------
    def _init_complete(self):
        """
        初始化完成的音频提示
        功能：系统上电初始化后，通过蜂鸣器播放两声短提示音，告知用户初始化完成
        异常：蜂鸣器驱动错误时，打印调试日志（仅enable_debug=True时）
        """
        try:
            self.buzzer.play_tone(CALIBRATION_BEEP_FREQ, CALIBRATION_BEEP_DUR)
            time.sleep_ms(100)  # 两声提示音之间的间隔（避免重叠）
            self.buzzer.play_tone(CALIBRATION_BEEP_FREQ, CALIBRATION_BEEP_DUR)
        except Exception as e:
            self._log(f"Initial beep error: {e}")  # 调试日志用英文（避免乱码）

    # -------------------------- 按键处理逻辑（注释中文，打印用英文） --------------------------
    def _check_button(self):
        """
        按键状态检测与事件判断
        功能：
        1. 检测按键按下/松开（带防抖处理，避免噪声误触发）
        2. 区分短按（50ms-1s）和长按（≥2s）：
           - 短按：切换任务暂停/恢复状态，更新LED指示
           - 长按：确认校准（仅任务运行时有效）
        """
        current_time = time.ticks_ms()

        # 检测按键按下（防抖：两次按下间隔需超过BUTTON_DEBOUNCE_MS）
        if self.button.value() == 0 and self.button_state == "released":
            if time.ticks_diff(current_time, self.button_last_press) > BUTTON_DEBOUNCE_MS:
                self.button_last_press = current_time
                self.button_state = "pressed"

        # 检测按键松开，计算按压时长并判断事件
        elif self.button.value() == 1 and self.button_state == "pressed":
            press_duration = time.ticks_diff(current_time, self.button_last_press)
            self.button_state = "released"

            # 短按事件（50ms ≤ 时长 ≤ 1s）：暂停/恢复任务
            if BUTTON_DEBOUNCE_MS <= press_duration <= SHORT_PRESS_MAX:
                self.task_paused = not self.task_paused
                # LED状态同步：运行时亮，暂停时灭
                self.led.on() if not self.task_paused else self.led.off()
                # 调试日志：打印任务状态（英文）
                self._log(f"Task {'resumed' if not self.task_paused else 'paused'} (short press)")
                # 任务暂停时，关闭报警（避免暂停后仍报警）
                if self.task_paused:
                    self._turn_off_alarm()

            # 长按事件（时长 ≥ 2s）：确认校准（仅任务运行时有效）
            elif press_duration >= LONG_PRESS_THRESHOLD and not self.task_paused:
                # 调试日志：打印长按检测结果（英文）
                self._log(f"Long press detected ({press_duration}ms ≥ 2000ms) - confirm calibration")
                # 触发校准确认逻辑
                self._confirm_calibration()

    # -------------------------- 校准流程方法（注释中文，打印用英文） --------------------------
    def _print_calibration_prompt(self):
        """
        打印校准阶段的操作说明（英文）
        功能：每个校准阶段（干燥/湿润）仅打印一次说明，避免重复输出
        说明：通过calibration_prompted标志控制，防止每次tick()都打印
        """
        if self.calibration_prompted:
            return  # 已打印过，直接返回
        # 干燥校准阶段说明
        if self.system_state == STATE_CALIBRATE_DRY:
            print("\n===== Dry Calibration Phase =====")
            print("1. Place sensor in dry air")
            print(f"2. Wait for {CALIBRATION_SAMPLES} samples (Progress: {len(self.calibration_samples)})")
            print("3. Hold button for 2 seconds to confirm")
            print("==================================\n")
        # 湿润校准阶段说明
        elif self.system_state == STATE_CALIBRATE_WET:
            print("\n===== Wet Calibration Phase =====")
            print("1. Place sensor in water or moist soil")
            print(f"2. Wait for {CALIBRATION_SAMPLES} samples (Progress: {len(self.calibration_samples)})")
            print("3. Hold button for 2 seconds to confirm")
            print("==================================\n")
        # 标记为已打印，避免重复
        self.calibration_prompted = True

    def _start_calibration(self, cal_type):
        """
        启动新的校准阶段（干燥或湿润）
        参数：
            cal_type：校准类型，需传入STATE_CALIBRATE_DRY或STATE_CALIBRATE_WET
        功能：
        1. 重置校准相关变量（样本缓冲区、提示标志、就绪标志）
        2. 打印当前阶段的操作说明
        3. 更新OLED显示，播放提示音
        """
        self.system_state = cal_type
        self.calibration_samples = []  # 清空历史样本
        self.calibration_prompted = False  # 重置提示标志（允许打印新说明）
        self.samples_ready = False  # 重置样本就绪标志
        self._print_calibration_prompt()  # 打印当前阶段说明
        self._update_display()  # 更新OLED显示校准状态
        self.buzzer.play_tone(CALIBRATION_BEEP_FREQ, CALIBRATION_BEEP_DUR)  # 播放提示音
        gc.collect()  # 垃圾回收，释放内存

    def _confirm_calibration(self):
        """
        确认校准（长按按键触发）
        功能：
        1. 检查样本数量：不足5个时，打印错误提示并播放失败音
        2. 样本足够时：计算平均ADC值，更新传感器校准参数
        3. 切换状态：干燥校准→湿润校准，湿润校准→正常监测
        """
        # 样本数量不足，校准失败
        if len(self.calibration_samples) < CALIBRATION_SAMPLES:
            needed = CALIBRATION_SAMPLES - len(self.calibration_samples)
            print(f"Calibration failed: Need {needed} more sample(s)")  # 英文打印错误
            # 播放双低音提示失败
            self.buzzer.play_tone(500, 300)
            time.sleep_ms(300)
            self.buzzer.play_tone(500, 300)
            return

        # 样本足够，计算平均ADC值（校准参考值）
        avg_adc = sum(self.calibration_samples) // len(self.calibration_samples)
        self.buzzer.play_tone(1500, 300)  # 播放高音提示成功

        # 干燥校准确认：更新干燥参考值，切换到湿润校准
        if self.system_state == STATE_CALIBRATE_DRY:
            current_dry, current_wet = self.soil_sensor.get_calibration()
            self.soil_sensor.set_calibration(dry=avg_adc, wet=current_wet)
            print(f"Dry calibration done! Reference value: {avg_adc} (Next: Wet calibration)")
            self._start_calibration(STATE_CALIBRATE_WET)

        # 湿润校准确认：更新湿润参考值，切换到正常监测
        elif self.system_state == STATE_CALIBRATE_WET:
            current_dry, current_wet = self.soil_sensor.get_calibration()
            self.soil_sensor.set_calibration(dry=current_dry, wet=avg_adc)
            print(f"Wet calibration done! Reference value: {avg_adc}")
            self.system_state = STATE_NORMAL  # 切换到正常监测
            self.calibration_completed = True  # 标记校准完成
            print("\n===== All Calibrations Done =====")
            print("System enters normal mode (Real-time moisture display)\n")
            gc.collect()  # 释放内存

    # -------------------------- 数据处理与报警逻辑（注释中文，打印用英文） ----------------------
    def _get_moisture_from_driver(self):
        """
        从传感器驱动获取计算后的湿度值
        功能：调用土壤传感器的read_moisture()方法，获取百分比湿度
        返回：湿度值（百分比，范围0.0-100.0，保留1位小数）
        异常：湿度计算失败时抛出Exception，含错误信息（英文）
        """
        try:
            return self.soil_sensor.read_moisture()
        except Exception as e:
            raise Exception(f"Moisture calculation error: {e}")  # 英文错误信息

    def _update_alarm_state(self):
        """
        更新系统报警状态
        功能：
        1. 仅在校准完成后生效（calibration_completed=True）
        2. 对比当前湿度与阈值：
           - 湿度 < 阈值：切换到报警状态（STATE_ALARM）
           - 湿度 ≥ 阈值：切换到正常状态（STATE_NORMAL），并关闭报警
        """
        if not self.calibration_completed:
            return  # 未校准，不更新报警状态
        self.system_state = STATE_ALARM if self.current_moisture < self.threshold else STATE_NORMAL
        # 切换到正常状态时，关闭报警（避免残留报警）
        if self.system_state == STATE_NORMAL:
            self._turn_off_alarm()

    def _handle_alarm_blink(self):
        """
        低湿度报警的LED闪烁与蜂鸣器控制
        功能：
        1. 按BLINK_INTERVAL_MS（500ms）间隔切换LED状态（亮/灭）
        2. 仅在LED亮时播放提示音（避免持续鸣叫，减少噪音）
        """
        current_time = time.ticks_ms()
        # 检查是否到闪烁间隔时间
        if time.ticks_diff(current_time, self.last_blink_time) >= BLINK_INTERVAL_MS:
            self.led_state = not self.led_state  # 切换LED状态
            self.last_blink_time = current_time  # 更新闪烁时间戳
            # 同步LED硬件状态
            self.led.on() if self.led_state else self.led.off()
            # 仅LED亮时播放提示音
            if self.led_state:
                self.buzzer.play_tone(1000, 400)

    def _turn_off_alarm(self):
        """
        关闭所有报警设备
        功能：
        1. 关闭LED（设置为灭）
        2. 停止蜂鸣器（播放0Hz静音音调）
        3. 重置LED状态标志（避免下次报警时状态异常）
        """
        self.led.off()
        self.buzzer.play_tone(0, 0)  # 0Hz=静音，停止蜂鸣器
        self.led_state = False

    # -------------------------- OLED显示更新（注释中文，显示用英文） --------------------------
    def _update_display(self):
        """
        更新OLED显示内容（适配128x64分辨率，避免文字超出屏幕）
        显示逻辑：
        1. 校准未完成：显示校准阶段、样本进度、确认提示
        2. 校准完成：显示实时湿度、报警阈值、系统状态
        3. 任务暂停：显示暂停提示与恢复方法
        """
        if not self.oled:
            return  # 未初始化OLED，直接返回
        try:
            self.oled.fill(0)  # 清屏（避免文字重叠）
            self.oled.text("Plant Monitor", 0, 0)  # 标题（顶部固定显示）

            # 校准阶段显示（未完成校准）
            if not self.calibration_completed:
                # 显示当前校准类型（干燥/湿润）
                cal_text = "Cal: Dry Air" if self.system_state == STATE_CALIBRATE_DRY else "Cal: Water"
                self.oled.text(cal_text, 0, 20)
                # 显示样本进度（格式：Samples: 已采集/总需求）
                self.oled.text(f"Samples: {len(self.calibration_samples)}/{CALIBRATION_SAMPLES}", 0, 36)
                # 样本就绪时，显示长按确认提示
                if self.samples_ready:
                    self.oled.text("Hold 2s to confirm", 0, 52)

            # 正常监测显示（已完成校准）
            else:
                # 显示当前湿度（简写Moisture为Moist，节省屏幕空间）
                self.oled.text(f"Moist: {self.current_moisture:.1f}%", 0, 16)
                # 显示当前报警阈值
                self.oled.text(f"Threshold: {self.threshold}%", 0, 32)
                # 显示系统状态（Normal/Need Water!）
                state_text = "Normal" if self.system_state == STATE_NORMAL else "Need Water!"
                self.oled.text(f"State: {state_text}", 0, 48)

            self.oled.show()  # 刷新屏幕，显示新内容
        except Exception as e:
            self._log(f"OLED display error: {e}")  # 调试日志用英文

    # -------------------------- 辅助函数与主任务逻辑（注释中文） --------------------------
    def _log(self, message):
        """
        调试日志打印（仅enable_debug=True时生效）
        参数：
            message：日志内容（英文，避免控制台乱码）
        功能：在控制台打印带前缀的调试信息，便于问题定位
        """
        if self.enable_debug:
            print(f"[Monitor] {message}")

    def tick(self):
        """
        主任务循环（由调度器按固定间隔调用，默认200ms）
        执行顺序：
        1. 按键检测（优先处理用户交互）
        2. 任务暂停判断（暂停时仅显示暂停提示）
        3. 校准流程（未完成校准时）
        4. 正常监测（完成校准时：湿度检测→阈值更新→报警控制→OLED显示）
        """
        current_time = time.ticks_ms()
        self._check_button()  # 1. 优先处理按键

        # 2. 任务暂停：仅显示暂停提示，不执行其他逻辑
        if self.task_paused:
            self.oled.fill(0)
            self.oled.text("Task Paused", 0, 20)
            self.oled.text("Short press to run", 0, 36)
            self.oled.show()
            return

        # 3. 校准流程（未完成校准时）
        if not self.calibration_completed:
            self._print_calibration_prompt()  # 打印校准说明（仅一次）
            # 样本不足时，继续采集
            if len(self.calibration_samples) < CALIBRATION_SAMPLES:
                try:
                    adc = self._read_soil_adc()  # 读取传感器原始值
                    self.calibration_samples.append(adc)  # 加入样本缓冲区
                    # 按间隔打印样本进度（英文）
                    if len(self.calibration_samples) % PRINT_INTERVAL == 0 or len(
                            self.calibration_samples) == CALIBRATION_SAMPLES:
                        print(f"Samples collected: {len(self.calibration_samples)}/{CALIBRATION_SAMPLES}")
                    # 样本足够时，标记就绪并提示
                    if len(self.calibration_samples) == CALIBRATION_SAMPLES and not self.samples_ready:
                        self.samples_ready = True
                        print("\nSample collection done! Hold button 2s \n")
                        # 播放双提示音，告知样本就绪
                        self.buzzer.play_tone(1200, 200)
                        time.sleep_ms(100)
                        self.buzzer.play_tone(1200, 200)
                except Exception as e:
                    print(f"Error: {e}")  # 英文错误信息
                    time.sleep_ms(1000)  # 出错后等待1秒再重试，避免频繁报错
            self._update_display()  # 更新OLED校准进度
            return

        # 4. 正常监测流程（完成校准时）
        # 按间隔检测湿度（默认2000ms）
        if time.ticks_diff(current_time, self.last_check_time) >= CHECK_INTERVAL_MS:
            self.last_check_time = current_time
            gc.collect()  # 垃圾回收，释放内存

            # 读取并更新当前湿度
            try:
                self.current_moisture = self._get_moisture_from_driver()
                print(f"Current moist: {self.current_moisture:.1f}%")  # 英文打印湿度
            except Exception as e:
                print(f"Moisture read error: {e}")  # 英文错误信息

            # 读取并更新报警阈值（滑动变阻器调节）
            try:
                ratio = self._read_potentiometer_ratio()
                self.threshold = int(ratio * 100)  # 比例→百分比（0-100%）
                print(f"Current threshold: {self.threshold}%")  # 英文打印阈值
            except Exception as e:
                print(f"Threshold read error: {e}")  # 英文错误信息

            self._update_alarm_state()  # 更新报警状态

        # 处理报警（仅报警状态时）
        if self.system_state == STATE_ALARM:
            self._handle_alarm_blink()
        else:
            self._turn_off_alarm()

        self._update_display()  # 更新OLED实时数据

    def emergency_stop(self):
        """
        紧急停止功能
        功能：
        1. 强制切换系统到正常状态（STATE_NORMAL）
        2. 关闭所有报警设备（LED+蜂鸣器）
        3. 打印紧急停止日志（仅调试模式）
        用于：意外情况或手动紧急停止报警
        """
        self.system_state = STATE_NORMAL
        self._turn_off_alarm()
        self._log("Emergency stop activated")  # 英文调试日志
