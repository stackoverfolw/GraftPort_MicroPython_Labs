# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/10 上午11:45   
# @Author  : 李清水            
# @File    : maintenance.py       
# @Description :  维护定期相关的任务，功能比较固定
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# 导入硬件相关模块
import gc
import sys
import time

# 导入配置相关的模块
# 先尝试包相对导入（适用于 tasks 作为包的情况）
conf = None
try:
    # type: ignore
    from .. import conf
except Exception:
    # 回退到绝对导入（适用于直接运行 main.py 的常见项目结构）
    try:
        # type: ignore
        import conf
    except Exception:
        conf = None
    else:
        conf = conf
else:
    conf = conf

# ======================================== 全局变量 ============================================

# 从 conf 中读取阈值与延时，若 conf 不可用则使用默认值
GC_THRESHOLD_BYTES = getattr(conf, "GC_THRESHOLD_BYTES", 100000)
ERROR_REPEAT_DELAY_S = getattr(conf, "ERROR_REPEAT_DELAY_S", 1.0)

__all__ = ["task_idle_callback", "task_err_callback", "GC_THRESHOLD_BYTES", "ERROR_REPEAT_DELAY_S"]

# ======================================== 功能函数 ============================================

def task_idle_callback() -> None:
    """
    空闲回调：当可用堆内存低于 GC_THRESHOLD_BYTES 时触发垃圾回收（gc.collect）。

    Notes:
        - 函数应尽量短小并容错，避免在调度器回调中抛出异常。
        - GC_THRESHOLD_BYTES 可通过 conf.py 配置覆盖。
    """
    try:
        free = gc.mem_free()
    except Exception:
        # 在极少见的平台上 gc.mem_free 可能不可用；直接返回
        return

    try:
        if free < GC_THRESHOLD_BYTES:
            # 轻量日志，仅在能打印时尝试（避免阻塞）
            try:
                print("task_idle: low memory ({} bytes). running gc.collect()".format(free))
            except Exception:
                pass
            try:
                gc.collect()
            except Exception:
                # 容错：若 gc.collect 出错，忽略以保证调度继续运行
                pass
    except Exception:
        # 总体保护：任何异常都不应从空闲回调抛出
        try:
            print("task_idle_callback unexpected error")
        except Exception:
            pass

def task_err_callback(e: Exception) -> None:
    """
    任务异常回调：打印异常信息并做限速（防止刷屏）。

    Args:
        e (Exception): 调度器捕获到的异常对象。

    Behavior:
        - 使用 sys.print_exception 输出完整回溯（若可用）。
        - 若 print_exception 不可用或抛出错误，回退到 print(repr(e))。
        - 在打印后 sleep ERROR_REPEAT_DELAY_S 秒以限速。
    """
    try:
        # 优先打印完整回溯
        try:
            sys.print_exception(e)
        except Exception:
            # 回退到简短输出
            try:
                print("task error:", repr(e))
            except Exception:
                pass
    except Exception:
        # 防御性捕获，确保 callback 不抛异常
        try:
            print("task_err_callback: failed to print exception")
        except Exception:
            pass

    # 限速打印，避免在短时间内反复刷屏
    try:
        time.sleep(ERROR_REPEAT_DELAY_S)
    except Exception:
        # 在某些环境 time.sleep 可能不可用或受限，忽略异常
        pass

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================