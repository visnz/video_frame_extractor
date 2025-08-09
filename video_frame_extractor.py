import os
import sys
import subprocess
import threading
import re
from tkinter import Tk, filedialog, messagebox, ttk, LabelFrame, Button, DoubleVar, Label
import webbrowser

class VideoProcessor:
    def __init__(self, root):
        self.root = root
        self.stop_requested = False
        self.setup_ui()

    def setup_ui(self):
        self.root.title("视频关键帧截取工具 v2.1")
        self.root.geometry("550x450")

        # 文件选择区域
        file_frame = LabelFrame(self.root, text="视频文件", padx=5, pady=5)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.entry_input = ttk.Entry(file_frame, width=40)
        self.entry_input.pack(side="left", padx=5)
        
        ttk.Button(file_frame, text="浏览...", command=self.browse_file).pack(side="left")

        # 参数设置区域
        param_frame = LabelFrame(self.root, text="处理参数", padx=5, pady=5)
        param_frame.pack(fill="x", padx=10, pady=5)

        # 阈值设置
        ttk.Label(param_frame, text="识别敏感度:").grid(row=0, column=0, sticky="w")
        self.threshold = DoubleVar(value=0.17)
        ttk.Entry(param_frame, textvariable=self.threshold, width=5).grid(row=0, column=1, sticky="w")
        ttk.Button(param_frame, text="?", width=2, command=self.show_threshold_help).grid(row=0, column=2, padx=5)

        # 操作按钮区域
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_run = ttk.Button(btn_frame, text="开始处理", command=self.start_processing)
        self.btn_run.pack(side="left", padx=5)
        
        self.btn_stop = ttk.Button(btn_frame, text="强制停止截图", state="disabled", command=self.request_stop)
        self.btn_stop.pack(side="left", padx=5)
        
        ttk.Button(btn_frame, text="打开输出目录", command=self.open_output_dir).pack(side="right")
        ttk.Button(btn_frame, text="?", width=2, command=self.show_output_help).pack(side="right")

        # 进度显示区域
        self.progress_frame = LabelFrame(self.root, text="处理进度", padx=5, pady=5)
        self.progress_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_label = ttk.Label(self.progress_frame, text="等待开始...")
        self.status_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")
        self.progress_bar.pack(fill="x", padx=10)

    def browse_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4 *.avi *.mov")])
        if filepath:
            self.entry_input.delete(0, "end")
            self.entry_input.insert(0, filepath)

    def show_threshold_help(self):
        messagebox.showinfo("敏感度说明",
            "阈值控制场景变化检测的敏感度：\n\n"
            "• 值越小 → 检测越敏感（可能捕获更多细微变化）\n"
            "• 值越大 → 检测越严格（只捕获显著变化）\n\n"
            "推荐值范围：0.15~0.3\n"
            "默认值：0.17")

    def show_output_help(self):
        messagebox.showinfo("输出路径说明",
            "输出文件将保存在：\n\n"
            "[输入视频所在文件夹]/\n"
            "[视频文件名]_clip/\n\n"
            "例如：\n"
            "输入：D:/videos/example.mp4\n"
            "输出：D:/videos/example_clip/")

    def start_processing(self):
        input_file = self.entry_input.get()
        if not input_file:
            messagebox.showerror("错误", "请先选择视频文件")
            return

        # 准备输出目录 (视频文件所在目录_clip)
        output_dir = os.path.join(
            os.path.dirname(input_file),
            f"{os.path.splitext(os.path.basename(input_file))[0]}_clip"
        )
        os.makedirs(output_dir, exist_ok=True)

        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.stop_requested = False
        self.progress_bar["value"] = 0
        self.status_label.config(text="准备开始...")

        threading.Thread(
            target=self.process_video,
            args=(input_file, output_dir),
            daemon=True
        ).start()

    def process_video(self, input_file, output_dir):
        try:
            # 第一步：场景检测
            self.update_status("正在计算场景变化（每20分钟输入视频，处理约需要2分钟）...", 20)
            
            try:
                cmd = [
                    self.get_ffmpeg_path(),
                    "-i", input_file,
                    "-vf", f"select='gt(scene,{self.threshold.get()})',showinfo",
                    "-f", "null",
                    "-"
                ]
                result = self.run_command(cmd, capture_output=True)
            except FileNotFoundError as e:
                messagebox.showerror(
                    "FFmpeg未找到",
                    "请确保：\n"
                    "1. ffmpeg.exe文件在该工具旁边\n"
                    "2. 或者已全局安装FFmpeg并添加到系统PATH\n\n"
                    "错误详情：" + str(e)
                )
                return
            
            if self.stop_requested:
                return

            # 第二步：提取时间戳
            self.update_status("正在分析时间点...", 40)
            timestamps = []
            for line in result.stderr.split('\n'):
                if self.stop_requested:
                    return
                if "pts_time:" in line:
                    match = re.search(r"pts_time:(\d+\.\d+)", line)
                    if match:
                        timestamps.append(float(match.group(1)))
            
            if self.stop_requested:
                return

            # 第三步：筛选关键帧
            self.update_status("正在筛选关键帧...", 60)
            filtered = []
            if timestamps:  # 确保列表不为空
                prev = timestamps[0]
                filtered.append(prev)
                for ts in timestamps[1:]:
                    if self.stop_requested:
                        return
                    if ts - prev >= 0.15:  # 固定间隔阈值
                        filtered.append(ts)
                        prev = ts
            
            if self.stop_requested:
                return

            # 第四步：批量截图
            self.update_status("正在截取关键帧...", 80)
            total = len(filtered)
            for i, ts in enumerate(filtered):
                if self.stop_requested:
                    return
                
                output_file = os.path.join(output_dir, f"frame_{ts:.3f}.png")
                self.run_command([
                    self.get_ffmpeg_path(),
                    "-ss", str(ts),
                    "-i", input_file,
                    "-vframes", "1",
                    "-q:v", "2",
                    output_file,
                    "-y",
                    "-loglevel", "quiet"
                ])
                
                progress = 80 + (20 * (i + 1) / total)
                self.update_status(f"截取进度: {i+1}/{total}", progress)

            if not self.stop_requested:
                self.update_status("处理完成！", 100)
                messagebox.showinfo("完成", f"已保存到：\n{output_dir}")

        except Exception as e:
            if not self.stop_requested:
                messagebox.showerror("错误", f"处理失败: {str(e)}")
        finally:
            self.root.after(0, self.reset_ui)

    def get_ffmpeg_path(self):
        """获取ffmpeg路径，优先检查同级目录"""
        # 检查同级目录
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        local_ffmpeg = os.path.join(exe_dir, "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        
        # 检查系统PATH
        try:
            subprocess.run(["ffmpeg", "-version"], 
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
            return "ffmpeg"
        except FileNotFoundError:
            raise FileNotFoundError("未找到ffmpeg.exe")

    def run_command(self, cmd, capture_output=False):
        """静默运行命令并返回结果"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        if capture_output:
            return subprocess.run(
                cmd,
                startupinfo=startupinfo,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.run(
                cmd,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

    def update_status(self, message, progress):
        self.root.after(0, lambda: [
            self.status_label.config(text=message),
            self.progress_bar.config(value=progress)
        ])

    def request_stop(self):
        self.stop_requested = True
        self.status_label.config(text="正在停止...")
        self.btn_stop.config(state="disabled")

    def reset_ui(self):
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")

    def open_output_dir(self):
        input_file = self.entry_input.get()
        if not input_file:
            messagebox.showerror("错误", "请先选择视频文件")
            return
            
        output_dir = os.path.join(
            os.path.dirname(input_file),
            f"{os.path.splitext(os.path.basename(input_file))[0]}_clip"
        )
        
        if os.path.exists(output_dir):
            webbrowser.open(output_dir)
        else:
            messagebox.showwarning("提示", "输出目录不存在，请先处理视频")

if __name__ == "__main__":
    root = Tk()
    app = VideoProcessor(root)
    root.mainloop()