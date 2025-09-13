import os
import sys
import subprocess
import threading
import re
from tkinter import Tk, filedialog, messagebox, ttk, LabelFrame, Button, DoubleVar, Label, Listbox, END, Scrollbar, MULTIPLE, StringVar, Checkbutton, BooleanVar
import webbrowser

class VideoProcessor:
    def __init__(self, root):
        self.root = root
        self.stop_requested = False
        self.setup_ui()

    def setup_ui(self):
        self.root.title("视频关键帧截取工具 v2.3")
        self.root.geometry("650x600")

        # 文件选择区域 - 改为多文件选择
        file_frame = LabelFrame(self.root, text="视频文件", padx=5, pady=5)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        # 创建列表框和滚动条用于多文件选择
        listbox_frame = ttk.Frame(file_frame)
        listbox_frame.pack(fill="x", padx=5, pady=5)
        
        self.listbox = Listbox(listbox_frame, height=4, selectmode=MULTIPLE)
        scrollbar = Scrollbar(listbox_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side="left", fill="x", expand=True, padx=(0, 5))
        scrollbar.pack(side="right", fill="y")
        
        # 按钮框架
        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="添加文件...", command=self.add_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="添加文件夹...", command=self.add_folder).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="移除选中", command=self.remove_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_list).pack(side="left", padx=5)

        # 参数设置区域
        param_frame = LabelFrame(self.root, text="处理参数", padx=5, pady=5)
        param_frame.pack(fill="x", padx=10, pady=5)

        # 阈值设置
        ttk.Label(param_frame, text="识别敏感度:").grid(row=0, column=0, sticky="w")
        self.threshold = DoubleVar(value=0.17)
        ttk.Entry(param_frame, textvariable=self.threshold, width=5).grid(row=0, column=1, sticky="w")
        ttk.Button(param_frame, text="?", width=2, command=self.show_threshold_help).grid(row=0, column=2, padx=5)

        # 图片格式选择区域
        format_frame = LabelFrame(self.root, text="输出设置", padx=5, pady=5)
        format_frame.pack(fill="x", padx=10, pady=5)

        # 图片格式选择
        ttk.Label(format_frame, text="图片格式:").grid(row=0, column=0, sticky="w", padx=5)
        self.image_format = StringVar(value="jpg")
        ttk.Combobox(format_frame, textvariable=self.image_format, 
                    values=["jpg", "png"], width=8, state="readonly").grid(row=0, column=1, sticky="w", padx=5)
        
        # 缩放选项
        self.scale_half = BooleanVar(value=False)
        Checkbutton(format_frame, text="缩放为一半尺寸", variable=self.scale_half).grid(row=0, column=2, sticky="w", padx=20)
        
        ttk.Button(format_frame, text="?", width=2, command=self.show_format_help).grid(row=0, column=3, padx=5)

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
        
        # 当前处理文件标签
        self.current_file_label = ttk.Label(self.progress_frame, text="")
        self.current_file_label.pack(pady=5)

    def is_supported_format(self, filename):
        """检查文件格式是否支持"""
        supported_formats = ('.mp4', '.avi', '.mov', '.mkv')
        return filename.lower().endswith(supported_formats)
    
    def add_files(self):
        """添加文件到列表"""
        files = filedialog.askopenfilenames(
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv")]
        )
        for file in files:
            if file not in self.listbox.get(0, END):
                self.listbox.insert(END, file)
    
    def add_folder(self):
        """添加文件夹中的所有视频文件"""
        folder = filedialog.askdirectory(title="选择包含视频文件的文件夹")
        if folder:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath) and self.is_supported_format(filename) and filepath not in self.listbox.get(0, END):
                    self.listbox.insert(END, filepath)
    
    def remove_selected(self):
        """移除选中的文件"""
        selected = self.listbox.curselection()
        for index in selected[::-1]:  # 从后往前删除，避免索引变化
            self.listbox.delete(index)
    
    def clear_list(self):
        """清空文件列表"""
        self.listbox.delete(0, END)

    def show_threshold_help(self):
        messagebox.showinfo("敏感度说明",
            "阈值控制场景变化检测的敏感度：\n\n"
            "• 值越小 → 检测越敏感（可能捕获更多细微变化）\n"
            "• 值越大 → 检测越严格（只捕获显著变化）\n\n"
            "推荐值范围：0.15~0.3\n"
            "默认值：0.17")

    def show_format_help(self):
        messagebox.showinfo("输出格式说明",
            "图片格式选项：\n\n"
            "• JPG - 较小的文件大小，有损压缩\n"
            "• PNG - 较大的文件大小，无损压缩\n\n"
            "缩放选项：\n"
            "• 启用后，图片尺寸将缩小为原始尺寸的一半")

    def show_output_help(self):
        messagebox.showinfo("输出路径说明",
            "输出文件将保存在：\n\n"
            "[输入视频所在文件夹]/\n"
            "[视频文件名]_clip/\n\n"
            "例如：\n"
            "输入：D:/videos/example.mp4\n"
            "输出：D:/videos/example_clip/")

    def start_processing(self):
        files = self.listbox.get(0, END)
        if not files:
            messagebox.showerror("错误", "请先添加视频文件")
            return

        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.stop_requested = False
        self.progress_bar["value"] = 0
        self.status_label.config(text="准备开始批量处理...")

        threading.Thread(
            target=self.process_multiple_videos,
            args=(files,),
            daemon=True
        ).start()

    def process_multiple_videos(self, files):
        """批量处理多个视频文件"""
        total_files = len(files)
        for i, input_file in enumerate(files):
            if self.stop_requested:
                break
                
            # 更新当前处理文件显示
            self.update_current_file(f"正在处理: {os.path.basename(input_file)} ({i+1}/{total_files})")
            
            # 准备输出目录 (视频文件所在目录_clip)
            output_dir = os.path.join(
                os.path.dirname(input_file),
                f"{os.path.splitext(os.path.basename(input_file))[0]}_clip"
            )
            os.makedirs(output_dir, exist_ok=True)

            # 处理单个视频
            self.process_video(input_file, output_dir, i, total_files)
            
        if not self.stop_requested:
            self.update_status("批量处理完成！", 100)
            messagebox.showinfo("完成", f"已处理 {len(files)} 个视频文件")

    def process_video(self, input_file, output_dir, file_index, total_files):
        try:
            # 计算进度范围 (每个文件占 100/total_files %)
            progress_per_file = 100 / total_files
            start_progress = file_index * progress_per_file
            
            # 第一步：场景检测
            self.update_status("正在计算场景变化...", start_progress + progress_per_file * 0.2)
            
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
                self.update_status(f"错误: {str(e)}", start_progress)
                return
            
            if self.stop_requested:
                return

            # 第二步：提取时间戳
            self.update_status("正在分析时间点...", start_progress + progress_per_file * 0.4)
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
            self.update_status("正在筛选关键帧...", start_progress + progress_per_file * 0.6)
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
            self.update_status("正在截取关键帧...", start_progress + progress_per_file * 0.8)
            total_frames = len(filtered)
            for j, ts in enumerate(filtered):
                if self.stop_requested:
                    return
                
                # 构建输出文件名
                output_file = os.path.join(output_dir, f"frame_{ts:.3f}.{self.image_format.get()}")
                
                # 构建ffmpeg命令
                ffmpeg_cmd = [
                    self.get_ffmpeg_path(),
                    "-ss", str(ts),
                    "-i", input_file,
                    "-vframes", "1"
                ]
                
                # 添加缩放滤镜（如果启用）
                if self.scale_half.get():
                    ffmpeg_cmd.extend(["-vf", "scale=iw/2:ih/2"])
                
                # 添加质量参数和输出文件
                if self.image_format.get() == "jpg":
                    ffmpeg_cmd.extend(["-q:v", "2"])  # JPG质量参数
                # PNG默认使用无损压缩，不需要额外质量参数
                
                ffmpeg_cmd.extend([
                    output_file,
                    "-y",
                    "-loglevel", "quiet"
                ])
                
                self.run_command(ffmpeg_cmd)
                
                frame_progress = start_progress + progress_per_file * (0.8 + 0.2 * (j + 1) / total_frames)
                self.update_status(f"截取进度: {j+1}/{total_frames}", frame_progress)

            if not self.stop_requested:
                self.update_status(f"完成文件 {file_index+1}/{total_files}", start_progress + progress_per_file)

        except Exception as e:
            if not self.stop_requested:
                self.update_status(f"处理失败: {str(e)}", start_progress)
        finally:
            if file_index == total_files - 1:  # 如果是最后一个文件
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
        
    def update_current_file(self, message):
        self.root.after(0, lambda: self.current_file_label.config(text=message))

    def request_stop(self):
        self.stop_requested = True
        self.status_label.config(text="正在停止...")
        self.btn_stop.config(state="disabled")

    def reset_ui(self):
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.current_file_label.config(text="")

    def open_output_dir(self):
        files = self.listbox.get(0, END)
        if not files:
            messagebox.showerror("错误", "请先添加视频文件")
            return
            
        # 打开第一个文件的输出目录
        input_file = files[0]
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