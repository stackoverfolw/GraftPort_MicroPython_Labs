pip install mpy_cross

生成依赖分析文件
python tools/dependency_analyzer.py -o build/dependencies.md --visualize build/dependencies.html

顺序编译mpy文件
python tools/mpy_compiler.py -s firmware -o build/firmware_mpy -vv

批量上传mpy文件
python tools/mpy_uploader.py -s build/firmware_mpy -a

查看当前设备中的mpy文件
python tools/mpy_uploader.py -l