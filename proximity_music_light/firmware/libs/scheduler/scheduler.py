# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2024/7/11 上午9:47
# @Author  : 李清水
# @File    : scheduler.py
# @Description : 自定义任务调度类
# @License : MIT
# 代码参考：https://github.com/micropython-Chinese-Community/micropython-simple-scheduler/tree/main

__version__ = "1.0.0"
__author__ = "shaoziyang"
__license__ = "MIT"
__platform__ = "MicroPython v1.23"
__chip__ = "All"

# ======================================== 导入相关模块 ========================================

# 导入const常量标识符
from micropython import const
# 导入硬件相关模块
from machine import Timer

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 定义Task任务类
class Task():
    """
    Task类，用于表示一个定时执行的任务，包含任务的回调函数、参数、执行间隔和任务状态。

    该类允许任务根据设定的时间间隔重复执行，并支持暂停和恢复任务。可以用于实现定时任务调度等功能。

    Attributes:
        TASK_RUN (int): 任务运行状态标识符，值为0，表示任务正在运行。
        TASK_STOP (int): 任务停止状态标识符，值为1，表示任务已停止。
        _callback (callable): 执行任务的回调函数，任务执行时调用。
        _param (tuple): 任务回调函数的参数。
        _intv (int): 任务执行的时间间隔，单位为毫秒，默认值为1000ms。
        _state (int): 任务状态，默认为 TASK_RUN，表示任务正在运行。
        _cnt (int): 任务计数器，表示任务已执行的次数，默认值为10。
        _rt (int): 任务执行的返回值或其他辅助信息，默认值为0。

    Methods:
        __init__(self, callback, *param, interval=1000, state=TASK_RUN) -> None:
            初始化Task类实例，设置回调函数、参数、间隔时间和任务状态。

        pause(self) -> None:
            暂停任务，将任务状态设置为TASK_STOP。

        resume(self) -> None:
            恢复任务，将任务状态设置为TASK_RUN。

        run(self) -> None:
            执行任务回调函数，并传入相关参数。
    """

    # 任务状态标识符
    TASK_RUN  = const(0)
    TASK_STOP = const(1)

    def __init__(self, callback: callable, *param: object, interval: int = 1000, state: int = TASK_RUN) -> None:
        """
        初始化Task类实例，设置回调函数、参数、执行间隔时间和任务状态。

        Args:
            callback (callable): 任务执行时调用的回调函数。
            *param (object): 传递给回调函数的参数。
            interval (int, optional): 任务执行的时间间隔，单位为毫秒。默认为1000ms。
            state (int, optional): 任务的初始状态，默认为TASK_RUN，表示任务正在运行。

        Returns:
            None
        """
        self._callback = callback
        self._param = param
        self._intv = interval
        self._state = state
        self._cnt = 10
        self._rt = 0

    def pause(self) -> None:
        """
        暂停任务，将任务状态设置为TASK_STOP。

        Args:
            None

        Returns:
            None
        """
        self._state = Task.TASK_STOP

    def resume(self) -> None:
        """
        恢复任务，将任务状态设置为TASK_RUN。

        Args:
            None

        Returns:
            None
        """
        self._state = Task.TASK_RUN

    def run(self) -> None:
        """
        执行任务回调函数，并传入相关参数。

        Args:
            None

        Returns:
            None
        """
        self._callback(*self._param)

# 定义Scheduler调度类
class Scheduler():
    """
    Scheduler 类，用于管理和调度任务的执行。

    该类通过定时器实现任务的周期性调度，支持任务的添加、删除、暂停、恢复和执行。
    任务可以是任意可调用对象，调度器会根据设定的时间间隔定期检查并执行任务。
    此外，调度器还支持任务空闲和任务错误的回调函数，用于处理任务执行过程中的特殊情况。

    Attributes:
        tm (machine.Timer): 定时器实例，用于触发任务的调度。
        interval (int): 定时器的时间间隔，单位为毫秒。
        task_idle (callable): 任务空闲时调用的回调函数。
        task_err (callable): 任务执行出错时调用的回调函数。
        tasks (list): 任务列表，存储所有已注册的任务实例。

    Methods:
        __init__(self, tm: Timer, interval: int = 100, task_idle: callable = None, task_err: callable = None):
            初始化调度器实例，设置定时器、时间间隔和回调函数。

        _tmrirq(self, t: Timer) -> None:
            定时器中断回调函数，用于触发任务的调度。

        _run(self, task: Task) -> None:
            执行单个任务的回调函数。

        scheduler(self) -> None:
            调度器的主循环，负责循环执行所有已注册的任务。

        find(self, task: Task) -> int:
            查找指定任务在任务列表中的索引。

        clear(self) -> None:
            清空任务列表。

        add(self, task: Task, state: int = Task.TASK_RUN) -> None:
            添加任务到任务列表中。

        delete(self, task: Task) -> None:
            从任务列表中删除指定任务。

        pause(self, task: Task) -> None:
            暂停指定任务的执行。

        resume(self, task: Task) -> None:
            恢复指定任务的执行。

        run(self, task: Task) -> None:
            执行指定任务的回调函数。
    """

    def __init__(self, tm: Timer, interval: int = 100, task_idle: callable = None,
                 task_err: callable = None) -> None:
        """
        初始化调度类实例，设置定时器、定时器间隔、任务空闲回调函数和任务错误回调函数。

        Args:
            tm (machine.Timer): 定时器实例，用于调度任务。
            interval (int, optional): 定时器间隔，单位为毫秒。默认为100ms。
            task_idle (callable, optional): 任务空闲时调用的回调函数，默认为None。
            task_err (callable, optional): 任务出现错误时调用的回调函数，默认为None。

        Returns:
            None
        """
        self._tasks     = []
        self._task_idle = task_idle
        self._task_err  = task_err
        self._interval  = interval
        self._tmr       = tm
        self._tmr.init(period=interval, callback=self._tmrirq)

    def _tmrirq(self, t: Timer) -> None:
        """
        定时器回调中断函数，用于处理定时器中断。

        Args:
            t (machine.Timer): 定时器实例，触发中断。

        Returns:
            None
        """
        # 遍历任务列表
        for i in range(len(self._tasks)):
            # 判断任务状态
            if self._tasks[i]._state == Task.TASK_RUN:
                # 任务_tasks[i]的执行时间间隔+1
                self._tasks[i]._rt += 1

    def _run(self, task: Task) -> None:
        """
        执行单个任务回调函数。

        Args:
            task (Task): 任务实例，包含需要执行的回调函数。

        Returns:
            None
        """
        # 判断任务状态是否为TASK_RUN
        if task._state == Task.TASK_RUN:
            try:
                # 判断任务执行时间间隔是否大于等于任务需要执行的时间间隔
                if task._rt >= task._cnt:
                    # 若是，则执行任务回调函数
                    task._rt = 0
                    task.run()
            except Exception as e:
                # 若是发生异常，则执行任务错误回调函数
                if self._task_err:
                    self._task_err(e)

    def scheduler(self) -> None:
        """
        调度器的主循环，负责循环执行所有已注册的任务。

        Args:
            None

        Returns:
            None
        """

        # 轮询检测任务状态，判断是否执行任务
        while True:
            try:
                # 执行到达执行时间间隔的任务
                for i in range(len(self._tasks)):
                    task = self._tasks[i]
                    self._run(task)
                # 若空闲，则执行任务空闲回调函数
                if self._task_idle:
                    self._task_idle()
            except KeyboardInterrupt:
                return
            # 发生异常时，抛出异常位置和类型
            except Exception as e:
                print('except {}'.format(e))

    def find(self, task: Task) -> int:
        """
        查找指定任务在任务列表中的索引。

        Args:
            task (Task): 待查找的任务实例。

        Returns:
            int: 任务在任务列表中的索引。
        """
        try:
            return self._tasks.index(task)
        except:
            return None

    def clear(self) -> None:
        """
        清空任务列表。

        Args:
            None

        Returns:
            None
        """
        self._tasks.clear()

    def add(self, task: Task, state: int = Task.TASK_RUN) -> None:
        """
        添加任务到任务列表中。

        Args:
            task (Task): 任务实例，需要添加的任务。
            state (int, optional): 任务状态，默认为Task.TASK_RUN，表示任务正在运行。

        Returns:
            None
        """
        if self.find(task) == None:
            self._tasks.append(task)
            # task._cnt为任务需要执行的时间间隔
            # 任务需要执行的时间间隔 = 任务间隔 // 定时器间隔
            task._cnt = task._intv // self._interval
            print('add task:', task._callback.__name__)
        if state == Task.TASK_STOP:
            self.pause(task)

    def delete(self, task: Task) -> None:
        """
        删除任务。

        Args:
            task (Task): 任务实例，待删除的任务。

        Returns:
            None
        """
        try:
            # 删除指定任务
            self._tasks.remove(task)
        except:
            print('del task <', task, '> error')

    def pause(self, task: Task) -> None:
        """
        暂停任务。

        Args:
            task (Task): 任务实例，待暂停的任务。

        Returns:
            None
        """
        if self.find(task) != None:
            self._tasks[self.find(task)].pause()

    def resume(self, task: Task) -> None:
        """
        恢复任务。

        Args:
            task (Task): 任务实例，待恢复的任务。

        Returns:
            None
        """
        if self.find(task) != None:
            self._tasks[self.find(task)].resume()

    def run(self, task: Task) -> None:
        """
        执行任务回调函数。

        Args:
            task (Task): 任务实例，包含要执行的回调函数。

        Returns:
            None
        """
        if self.find(task) != None:
            task._rt = task._cnt
            self._run(task)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ============================================