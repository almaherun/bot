import asyncio
import logging
import os
import sys
import time
import glob
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from telegram import Bot, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

# إعداد الـ logging المتقدم
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('telegram_uploader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# إعدادات البوت
BOT_TOKEN = "7951915347:AAEauEVFZbQ6TizUNQalxJJOpMRLyNXOVF0"

# الثوابت
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
MAX_DOCUMENT_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp']
AUDIO_EXTENSIONS = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico']
DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx']
ARCHIVE_EXTENSIONS = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
CODE_EXTENSIONS = ['.py', '.js', '.html', '.css', '.cpp', '.c', '.java', '.php', '.go', '.rs']

class Colors:
    """ألوان للطباعة في الطرفية"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class TelegramVideoUploader:
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.current_path = os.getcwd()
        self.selected_files = []
        self.last_channels = []
        self.search_query = ""
        self.filter_type = None
        self.sort_by = "name"  # name, size, date
        self.sort_reverse = False
        self.bookmarks = []
        self.upload_history = []
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """تحميل الإعدادات من ملف"""
        config_path = os.path.expanduser("~/.telegram_uploader_config.json")
        default_config = {
            "default_upload_type": "auto",  # auto, video, document
            "default_caption": "📦 {filename}\n💾 الحجم: {size}",
            "auto_compress": False,
            "compress_quality": 28,
            "split_large_files": True,
            "split_size": "1.5GB",
            "upload_delay": 2,
            "theme": "default"
        }
        
        try:
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    default_config.update(config)
        except Exception as e:
            logger.error(f"خطأ في تحميل الإعدادات: {e}")
            
        return default_config
    
    def save_config(self):
        """حفظ الإعدادات إلى ملف"""
        config_path = os.path.expanduser("~/.telegram_uploader_config.json")
        try:
            import json
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ الإعدادات: {e}")
    
    def clear_screen(self):
        """مسح الشاشة"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self, title: str, subtitle: str = ""):
        """طباعة عنوان مع تزيين متقدم"""
        self.clear_screen()
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'🚀 ' + title:^78}{Colors.ENDC}")
        if subtitle:
            print(f"{Colors.CYAN}{subtitle:^80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
    
    def print_current_path(self):
        """عرض المسار الحالي بشكل جميل"""
        home_path = os.path.expanduser("~")
        display_path = self.current_path.replace(home_path, "~")
        print(f"{Colors.BLUE}📍 المسار الحالي: {display_path}{Colors.ENDC}")
        print(f"{Colors.BLUE}{'-' * 80}{Colors.ENDC}")
    
    def print_status_bar(self):
        """عرض شريط الحالة"""
        selected_count = len(self.selected_files)
        selected_size = sum(f['size'] for f in self.selected_files)
        current_time = datetime.now().strftime("%H:%M:%S")
        
        status = f"📊 مختار: {selected_count} ملف ({self.format_size(selected_size)}) | 🕒 {current_time}"
        if self.search_query:
            status += f" | 🔍 بحث: '{self.search_query}'"
        if self.filter_type:
            status += f" | 🎯 تصفية: {self.filter_type}"
        
        print(f"{Colors.GREEN}{status}{Colors.ENDC}")
        print(f"{Colors.BLUE}{'-' * 80}{Colors.ENDC}")
    
    async def get_bot_channels(self) -> List[Dict[str, Any]]:
        """الحصول على القنوات والجروبات التي البوت إدمن فيها"""
        if self.last_channels:
            return self.last_channels
            
        try:
            bot_info = await self.bot.get_me()
            print(f"{Colors.CYAN}🤖 البوت: {bot_info.first_name} (@{bot_info.username}){Colors.ENDC}")
            
            channels = []
            updates = await self.bot.get_updates(limit=100)
            
            for update in updates:
                if update.message and update.message.chat:
                    chat = update.message.chat
                    if chat.type in ['group', 'supergroup', 'channel']:
                        try:
                            chat_member = await self.bot.get_chat_member(chat.id, bot_info.id)
                            if chat_member.status in ['administrator', 'creator']:
                                channels.append({
                                    'id': chat.id,
                                    'title': chat.title,
                                    'type': chat.type,
                                    'username': getattr(chat, 'username', None)
                                })
                        except Exception:
                            continue
            
            # إزالة المكررات
            unique_channels = []
            seen_ids = set()
            for channel in channels:
                if channel['id'] not in seen_ids:
                    unique_channels.append(channel)
                    seen_ids.add(channel['id'])
            
            self.last_channels = unique_channels
            return unique_channels
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على القنوات: {e}")
            return []
    
    def scan_directory(self, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """فحص مجلد محدد مع دعم البحث والتصفية"""
        if path is None:
            path = self.current_path
            
        items = []
        
        try:
            all_items = os.listdir(path)
            folders = []
            files = []
            
            for item in all_items:
                # تطبيق البحث إذا كان موجود
                if self.search_query and self.search_query.lower() not in item.lower():
                    continue
                    
                item_path = os.path.join(path, item)
                try:
                    if os.path.isdir(item_path):
                        folders.append(item)
                    else:
                        files.append(item)
                except PermissionError:
                    continue
            
            # تطبيق الترتيب
            if self.sort_by == "name":
                folders.sort(reverse=self.sort_reverse)
                files.sort(reverse=self.sort_reverse)
            elif self.sort_by == "size":
                files.sort(key=lambda f: os.path.getsize(os.path.join(path, f)), reverse=self.sort_reverse)
            elif self.sort_by == "date":
                files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=self.sort_reverse)
            
            # إضافة خيار العودة للمجلد الأب
            if path != "/":
                items.append({
                    'name': "..",
                    'type': 'parent',
                    'path': os.path.dirname(path),
                    'size': 0,
                    'date': 0
                })
            
            # إضافة المجلدات
            for folder in folders:
                folder_path = os.path.join(path, folder)
                folder_stat = os.stat(folder_path)
                items.append({
                    'name': folder,
                    'type': 'folder',
                    'path': folder_path,
                    'size': self.get_folder_size(folder_path),
                    'date': folder_stat.st_mtime
                })
            
            # إضافة الملفات مع تطبيق التصفية
            for file in files:
                file_path = os.path.join(path, file)
                try:
                    file_stat = os.stat(file_path)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    # تطبيق التصفية
                    if self.filter_type:
                        if self.filter_type == "video" and file_ext not in VIDEO_EXTENSIONS:
                            continue
                        elif self.filter_type == "audio" and file_ext not in AUDIO_EXTENSIONS:
                            continue
                        elif self.filter_type == "image" and file_ext not in IMAGE_EXTENSIONS:
                            continue
                        elif self.filter_type == "document" and file_ext not in DOCUMENT_EXTENSIONS:
                            continue
                        elif self.filter_type == "archive" and file_ext not in ARCHIVE_EXTENSIONS:
                            continue
                        elif self.filter_type == "code" and file_ext not in CODE_EXTENSIONS:
                            continue
                    
                    items.append({
                        'name': file,
                        'type': 'file',
                        'path': file_path,
                        'size': file_stat.st_size,
                        'extension': file_ext,
                        'date': file_stat.st_mtime
                    })
                except OSError:
                    continue
            
        except PermissionError:
            print(f"{Colors.FAIL}❌ ليس لديك صلاحية الوصول لهذا المجلد!{Colors.ENDC}")
            return []
        except Exception as e:
            logger.error(f"خطأ في فحص المجلد: {e}")
            return []
        
        return items
    
    def get_folder_size(self, folder_path: str) -> int:
        """حساب حجم المجلد"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    try:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.exists(filepath):
                            total_size += os.path.getsize(filepath)
                    except (OSError, PermissionError):
                        continue
                # توقف عند 1000 ملف لتوفير الوقت
                if len(filenames) > 1000:
                    break
        except Exception:
            pass
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """تنسيق حجم الملف"""
        if size_bytes == 0:
            return "-"
        elif size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.2f} GB"
    
    def format_date(self, timestamp: float) -> str:
        """تنسيق التاريخ"""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    
    def display_items(self, items: List[Dict[str, Any]], page: int = 0, items_per_page: int = 15) -> Tuple[int, int]:
        """عرض الملفات والمجلدات مع تقسيم الصفحات"""
        if not items:
            print(f"{Colors.WARNING}📭 لا توجد ملفات أو مجلدات في هذا المجلد!{Colors.ENDC}")
            return 0, 0
        
        total_pages = (len(items) - 1) // items_per_page + 1
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        
        page_items = items[start_idx:end_idx]
        
        print(f"\n{Colors.CYAN}📋 محتويات المجلد (صفحة {page + 1} من {total_pages}):{Colors.ENDC}")
        print(f"{Colors.BLUE}{'=' * 85}{Colors.ENDC}")
        print(f"{'#':>3} {'نوع':>4} {'الاسم':<30} {'الحجم':>10} {'التاريخ':>16} {'مختار':>8}")
        print(f"{Colors.BLUE}{'-' * 85}{Colors.ENDC}")
        
        for i, item in enumerate(page_items, start_idx + 1):
            icon = self.get_item_icon(item)
            size_str = self.format_size(item['size'])
            date_str = self.format_date(item['date']) if 'date' in item else "N/A"
            selected = "✅" if item['path'] in [f['path'] for f in self.selected_files] else ""
            
            # قطع الاسم إذا كان طويلاً
            display_name = item['name']
            if len(display_name) > 28:
                display_name = display_name[:25] + "..."
            
            print(f"{i:3d} {icon:>4} {display_name:<30} {size_str:>10} {date_str:>16} {selected:>8}")
        
        print(f"{Colors.BLUE}{'=' * 85}{Colors.ENDC}")
        
        # إحصائيات
        total_files = len([item for item in items if item['type'] == 'file'])
        total_folders = len([item for item in items if item['type'] == 'folder'])
        selected_count = len(self.selected_files)
        
        print(f"{Colors.GREEN}📊 الإحصائيات: {total_folders} مجلد، {total_files} ملف | مختار: {selected_count} ملف{Colors.ENDC}")
        
        if total_pages > 1:
            print(f"{Colors.CYAN}📄 الصفحات: استخدم 'n' للصفحة التالية، 'p' للصفحة السابقة{Colors.ENDC}")
        
        return len(page_items), total_pages
    
    def get_item_icon(self, item: Dict[str, Any]) -> str:
        """الحصول على أيقونة العنصر"""
        if item['type'] == 'parent':
            return "⬆️"
        elif item['type'] == 'folder':
            return "📁"
        else:
            return self.get_file_icon(item.get('extension', ''))
    
    def get_file_icon(self, extension: str) -> str:
        """الحصول على أيقونة الملف حسب النوع"""
        if extension in VIDEO_EXTENSIONS:
            return "🎬"
        elif extension in AUDIO_EXTENSIONS:
            return "🎵"
        elif extension in IMAGE_EXTENSIONS:
            return "🖼️"
        elif extension in DOCUMENT_EXTENSIONS:
            return "📄"
        elif extension in ARCHIVE_EXTENSIONS:
            return "📦"
        elif extension in CODE_EXTENSIONS:
            return "💻"
        else:
            return "📄"
    
    def print_commands_help(self):
        """عرض قائمة الأوامر المتاحة بشكل متقدم"""
        print(f"\n{Colors.CYAN}🔧 الأوامر المتاحة:{Colors.ENDC}")
        print(f"{Colors.BLUE}{'-' * 50}{Colors.ENDC}")
        print(f"{Colors.GREEN}رقم         : {Colors.ENDC}فتح مجلد أو اختيار ملف")
        print(f"{Colors.GREEN}s + رقم     : {Colors.ENDC}إضافة/إزالة ملف من المختارات")
        print(f"{Colors.GREEN}a           : {Colors.ENDC}اختيار جميع الملفات")
        print(f"{Colors.GREEN}c           : {Colors.ENDC}مسح المختارات")
        print(f"{Colors.GREEN}u           : {Colors.ENDC}رفع الملفات المختارة")
        print(f"{Colors.GREEN}r           : {Colors.ENDC}تحديث المحتويات")
        print(f"{Colors.GREEN}h           : {Colors.ENDC}المجلد الرئيسي")
        print(f"{Colors.GREEN}n           : {Colors.ENDC}الصفحة التالية")
        print(f"{Colors.GREEN}p           : {Colors.ENDC}الصفحة السابقة")
        print(f"{Colors.GREEN}/ كلمة      : {Colors.ENDC}بحث عن ملفات")
        print(f"{Colors.GREEN}f نوع       : {Colors.ENDC}تصفية حسب النوع (video, audio, image, document, archive, code)")
        print(f"{Colors.GREEN}o نوع       : {Colors.ENDC}ترتيب حسب (name, size, date)")
        print(f"{Colors.GREEN}b           : {Colors.ENDC}إدارة الإشارات المرجعية")
        print(f"{Colors.GREEN}i           : {Colors.ENDC}معلومات عن الملف المحدد")
        print(f"{Colors.GREEN}q           : {Colors.ENDC}خروج")
        print(f"{Colors.BLUE}{'-' * 50}{Colors.ENDC}")
    
    def display_selected_files(self):
        """عرض الملفات المختارة بشكل متقدم"""
        if not self.selected_files:
            print(f"\n{Colors.WARNING}📭 لا توجد ملفات مختارة!{Colors.ENDC}")
            return
            
        total_size = sum(f['size'] for f in self.selected_files)
        print(f"\n{Colors.CYAN}📋 الملفات المختارة ({len(self.selected_files)} ملف - {self.format_size(total_size)}):{Colors.ENDC}")
        print(f"{Colors.BLUE}{'-' * 60}{Colors.ENDC}")
        
        for i, file in enumerate(self.selected_files[:10], 1):
            icon = self.get_file_icon(file.get('extension', ''))
            size = self.format_size(file['size'])
            date = self.format_date(file['date']) if 'date' in file else "N/A"
            name = file['name']
            if len(name) > 35:
                name = name[:32] + "..."
            print(f"{i:2d}. {icon} {name} [{size}] [{date}]")
        
        if len(self.selected_files) > 10:
            print(f"    ... و {len(self.selected_files) - 10} ملف آخر")
        print(f"{Colors.BLUE}{'-' * 60}{Colors.ENDC}")
    
    async def display_channels_interactive(self) -> Optional[Dict[str, Any]]:
        """عرض القنوات بشكل تفاعلي متقدم"""
        channels = await self.get_bot_channels()
        
        if not channels:
            print(f"\n{Colors.FAIL}❌ لم يتم العثور على قنوات!{Colors.ENDC}")
            print(f"{Colors.CYAN}💡 يمكنك إدخال معرف قناة يدوياً:{Colors.ENDC}")
            
            while True:
                manual_id = input(f"{Colors.GREEN}📺 معرف القناة (@username أو رقم) أو Enter للتخطي: {Colors.ENDC}").strip()
                if not manual_id:
                    return None
                if manual_id.startswith('@') or manual_id.lstrip('-').isdigit():
                    return {'id': manual_id, 'title': 'قناة مخصصة', 'type': 'manual'}
                print(f"{Colors.FAIL}❌ معرف غير صحيح! استخدم @username أو رقم{Colors.ENDC}")
        
        print(f"\n{Colors.CYAN}📺 القنوات المتاحة ({len(channels)} قناة):{Colors.ENDC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
        
        for i, channel in enumerate(channels, 1):
            icon = "📢" if channel['type'] == 'channel' else "👥"
            username = f"(@{channel['username']})" if channel.get('username') else ""
            title = channel['title'][:35] + "..." if len(channel['title']) > 35 else channel['title']
            print(f"{i:2d}. {icon} {title} {username}")
        
        print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
        
        while True:
            try:
                choice = input(f"{Colors.GREEN}🔢 اختر رقم القناة (1-{len(channels)}) أو 'm' لإدخال يدوي: {Colors.ENDC}").strip()
                
                if choice.lower() == 'm':
                    manual_id = input(f"{Colors.GREEN}📺 معرف القناة: {Colors.ENDC}").strip()
                    if manual_id:
                        return {'id': manual_id, 'title': 'قناة مخصصة', 'type': 'manual'}
                    continue
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(channels):
                    return channels[choice_num - 1]
                else:
                    print(f"{Colors.FAIL}❌ اختر رقم من 1 إلى {len(channels)}{Colors.ENDC}")
                    
            except ValueError:
                print(f"{Colors.FAIL}❌ أدخل رقم صحيح!{Colors.ENDC}")
    
    async def upload_file(self, file_info: Dict[str, Any], chat_id: str, current_num: int, total_num: int) -> Tuple[bool, str]:
        """رفع ملف واحد مع معلومات التقدم المتقدمة"""
        try:
            file_path = file_info['path']
            filename = file_info['name']
            file_size = file_info['size']
            
            if not os.path.exists(file_path):
                return False, f"الملف غير موجود: {filename}"
            
            # تحديد نوع الرفع
            ext = file_info.get('extension', '').lower()
            upload_type = self.config.get('default_upload_type', 'auto')
            
            caption = self.config.get('default_caption', "📦 {filename}\n💾 الحجم: {size}")
            caption = caption.replace('{filename}', filename)
            caption = caption.replace('{size}', self.format_size(file_size))
            caption += f"\n🔢 ملف {current_num} من {total_num}"
            
            print(f"{Colors.CYAN}📤 [{current_num}/{total_num}] {filename} ({self.format_size(file_size)}){Colors.ENDC}")
            
            # شريط التقدم
            progress_bar = self.create_progress_bar(0, 100, 30)
            print(f"{Colors.GREEN}[{progress_bar}]{Colors.ENDC} 0%")
            
            with open(file_path, 'rb') as file:
                if upload_type == 'auto':
                    if ext in VIDEO_EXTENSIONS and file_size <= MAX_VIDEO_SIZE:
                        message = await self.bot.send_video(
                            chat_id=chat_id,
                            video=file,
                            caption=caption,
                            supports_streaming=True,
                            read_timeout=60,
                            write_timeout=60,
                            connect_timeout=60,
                            pool_timeout=60
                        )
                    else:
                        message = await self.bot.send_document(
                            chat_id=chat_id,
                            document=file,
                            caption=caption,
                            read_timeout=60,
                            write_timeout=60,
                            connect_timeout=60,
                            pool_timeout=60
                        )
                elif upload_type == 'video':
                    if ext not in VIDEO_EXTENSIONS:
                        return False, f"الملف ليس فيديو: {filename}"
                    message = await self.bot.send_video(
                        chat_id=chat_id,
                        video=file,
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60,
                        connect_timeout=60,
                        pool_timeout=60
                    )
                else:  # document
                    message = await self.bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        caption=caption,
                        read_timeout=60,
                        write_timeout=60,
                        connect_timeout=60,
                        pool_timeout=60
                    )
            
            # تحديث شريط التقدم
            progress_bar = self.create_progress_bar(100, 100, 30)
            print(f"\r{Colors.GREEN}[{progress_bar}]{Colors.ENDC} 100%")
            
            # حفظ في التاريخ
            self.upload_history.append({
                'filename': filename,
                'size': file_size,
                'chat_id': chat_id,
                'timestamp': time.time(),
                'success': True
            })
            
            return True, f"تم رفع {filename} بنجاح"
            
        except Exception as e:
            error_msg = f"فشل رفع {filename}: {str(e)}"
            logger.error(error_msg)
            
            # حفظ في التاريخ
            self.upload_history.append({
                'filename': filename,
                'size': file_size,
                'chat_id': chat_id,
                'timestamp': time.time(),
                'success': False,
                'error': str(e)
            })
            
            return False, error_msg
    
    def create_progress_bar(self, current: int, total: int, width: int = 30) -> str:
        """إنشاء شريط تقدم"""
        if total == 0:
            return "[" + "=" * width + "]"
        
        progress = min(current / total, 1.0)
        filled = int(width * progress)
        bar = "=" * filled + "-" * (width - filled)
        return bar
    
    async def upload_selected_files(self):
        """رفع الملفات المختارة بشكل متقدم"""
        if not self.selected_files:
            print(f"{Colors.FAIL}❌ لا توجد ملفات مختارة!{Colors.ENDC}")
            input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
            return
        
        # عرض ملخص الملفات
        self.print_header("رفع الملفات المختارة")
        self.display_selected_files()
        
        # اختيار القناة
        selected_channel = await self.display_channels_interactive()
        if not selected_channel:
            print(f"{Colors.FAIL}❌ لم يتم اختيار قناة!{Colors.ENDC}")
            input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
            return
        
        print(f"{Colors.GREEN}✅ تم اختيار القناة: {selected_channel['title']}{Colors.ENDC}")
        
        # اختيار نوع الرفع
        upload_type = self.config.get('default_upload_type', 'auto')
        if upload_type == 'auto':
            print(f"{Colors.CYAN}📤 سيتم رع الملفات تلقائياً كفيديو أو وثيقة حسب النوع والحجم{Colors.ENDC}")
        else:
            print(f"{Colors.CYAN}📤 سيتم رفع الملفات كـ {upload_type}{Colors.ENDC}")
        
        # تأكيد الرفع
        confirm = input(f"\n{Colors.GREEN}🚀 رفع {len(self.selected_files)} ملف؟ (y/n): {Colors.ENDC}").strip().lower()
        if confirm != 'y':
            print(f"{Colors.FAIL}❌ تم إلغاء الرفع!{Colors.ENDC}")
            input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
            return
        
        # بدء الرفع
        print(f"\n{Colors.CYAN}🚀 بدء رفع {len(self.selected_files)} ملف...{Colors.ENDC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
        
        success_count = 0
        failed_files = []
        
        for i, file_info in enumerate(self.selected_files, 1):
            success, message = await self.upload_file(
                file_info, 
                selected_channel['id'], 
                i, 
                len(self.selected_files)
            )
            
            if success:
                success_count += 1
                print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")
            else:
                failed_files.append(file_info['name'])
                print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")
            
            # توقف بين الرفعات
            if i < len(self.selected_files):
                delay = self.config.get('upload_delay', 2)
                print(f"{Colors.CYAN}⏳ انتظار {delay} ثانية...{Colors.ENDC}")
                await asyncio.sleep(delay)
        
        # عرض النتائج
        print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.GREEN}🎉 انتهت عملية الرفع!{Colors.ENDC}")
        print(f"{Colors.GREEN}✅ نجح: {success_count}/{len(self.selected_files)}{Colors.ENDC}")
        
        if failed_files:
            print(f"{Colors.FAIL}❌ فشل في رفع: {', '.join(failed_files[:3])}{Colors.ENDC}")
            if len(failed_files) > 3:
                print(f"{Colors.FAIL}    و {len(failed_files) - 3} ملف آخر...{Colors.ENDC}")
        
        input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
    
    def display_file_info(self, file_path: str):
        """عرض معلومات مفصلة عن ملف"""
        try:
            file_stat = os.stat(file_path)
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            file_size = file_stat.st_size
            file_date = datetime.fromtimestamp(file_stat.st_mtime)
            
            self.print_header(f"معلومات الملف: {filename}")
            
            print(f"{Colors.CYAN}📄 اسم الملف: {Colors.ENDC}{filename}")
            print(f"{Colors.CYAN}📂 المسار: {Colors.ENDC}{file_path}")
            print(f"{Colors.CYAN}📏 الحجم: {Colors.ENDC}{self.format_size(file_size)}")
            print(f"{Colors.CYAN}📅 تاريخ التعديل: {Colors.ENDC}{file_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{Colors.CYAN}🔍 النوع: {Colors.ENDC}{self.get_file_type(file_ext)}")
            
            # معلومات إضافية للفيديو
            if file_ext in VIDEO_EXTENSIONS:
                try:
                    import subprocess
                    result = subprocess.run(
                        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,duration', '-of', 'csv=s=x:p=0', file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    if result.returncode == 0:
                        info = result.stdout.strip().split(',')
                        if len(info) >= 3:
                            width, height, duration = info[0], info[1], float(info[2])
                            print(f"{Colors.CYAN}🎬 أبعاد الفيديو: {Colors.ENDC}{width}x{height}")
                            print(f"{Colors.CYAN}⏱️ المدة: {Colors.ENDC}{int(duration//60):02d}:{int(duration%60):02d}")
                except Exception:
                    pass
            
            input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.FAIL}❌ خطأ في عرض معلومات الملف: {e}{Colors.ENDC}")
            input(f"\n{Colors.GREEN}⏎ اضغط Enter للمتابعة...{Colors.ENDC}")
    
    def get_file_type(self, extension: str) -> str:
        """الحصول على نوع الملف حسب الامتداد"""
        if extension in VIDEO_EXTENSIONS:
            return "فيديو"
        elif extension in AUDIO_EXTENSIONS:
            return "صوت"
        elif extension in IMAGE_EXTENSIONS:
            return "صورة"
        elif extension in DOCUMENT_EXTENSIONS:
            return "وثيقة"
        elif extension in ARCHIVE_EXTENSIONS:
            return "أرشيف"
        elif extension in CODE_EXTENSIONS:
            return "كود"
        else:
            return "ملف"
    
    def manage_bookmarks(self):
        """إدارة الإشارات المرجعية"""
        while True:
            self.print_header("إدارة الإشارات المرجعية")
            
            if not self.bookmarks:
                print(f"{Colors.WARNING}📭 لا توجد إشارات مرجعية!{Colors.ENDC}")
            else:
                print(f"{Colors.CYAN}📌 الإشارات المرجعية:{Colors.ENDC}")
                print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
                for i, bookmark in enumerate(self.bookmarks, 1):
                    name = bookmark['name']
                    path = bookmark['path']
                    if len(path) > 45:
                        path = path[:42] + "..."
                    print(f"{i:2d}. {name} - {path}")
                print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
            
            print(f"{Colors.CYAN}🔧 الأوامر:{Colors.ENDC}")
            print(f"{Colors.GREEN}a           : {Colors.ENDC}إضافة إشارة مرجعية للمسار الحالي")
            print(f"{Colors.GREEN}d + رقم     : {Colors.ENDC}حذف إشارة مرجعية")
            print(f"{Colors.GREEN}g + رقم     : {Colors.ENDC}الذهاب إلى الإشارة المرجعية")
            print(f"{Colors.GREEN}q           : {Colors.ENDC}خروج")
            
            command = input(f"\n{Colors.GREEN}💻 أدخل الأمر: {Colors.ENDC}").strip().lower()
            
            if command == 'q':
                break
            elif command == 'a':
                name = input(f"{Colors.GREEN}📌 اسم الإشارة المرجعية: {Colors.ENDC}").strip()
                if name:
                    self.bookmarks.append({
                        'name': name,
                        'path': self.current_path
                    })
                    print(f"{Colors.GREEN}✅ تمت إضافة الإشارة المرجعية!{Colors.ENDC}")
                    time.sleep(1)
            elif command.startswith('d '):
                try:
                    bookmark_num = int(command.split()[1])
                    if 1 <= bookmark_num <= len(self.bookmarks):
                        del self.bookmarks[bookmark_num - 1]
                        print(f"{Colors.GREEN}✅ تم حذف الإشارة المرجعية!{Colors.ENDC}")
                        time.sleep(1)
                    else:
                        print(f"{Colors.FAIL}❌ رقم غير صحيح!{Colors.ENDC}")
                        time.sleep(1)
                except (ValueError, IndexError):
                    print(f"{Colors.FAIL}❌ استخدم: d رقم_الإشارة{Colors.ENDC}")
                    time.sleep(1)
            elif command.startswith('g '):
                try:
                    bookmark_num = int(command.split()[1])
                    if 1 <= bookmark_num <= len(self.bookmarks):
                        self.current_path = self.bookmarks[bookmark_num - 1]['path']
                        print(f"{Colors.GREEN}✅ تم الانتقال إلى الإشارة المرجعية!{Colors.ENDC}")
                        time.sleep(1)
                        break
                    else:
                        print(f"{Colors.FAIL}❌ رقم غير صحيح!{Colors.ENDC}")
                        time.sleep(1)
                except (ValueError, IndexError):
                    print(f"{Colors.FAIL}❌ استخدم: g رقم_الإشارة{Colors.ENDC}")
                    time.sleep(1)
            else:
                print(f"{Colors.FAIL}❌ أمر غير مفهوم!{Colors.ENDC}")
                time.sleep(1)
    
    async def run_interactive_explorer(self):
        """تشغيل المستكشف التفاعلي المتقدم"""
        current_page = 0
        
        while True:
            # عرض المحتوى
            self.print_header("مستكشف الملفات التفاعلي - Telegram Uploader")
            self.print_current_path()
            self.print_status_bar()
            
            items = self.scan_directory(self.current_path)
            items_count, total_pages = self.display_items(items, current_page)
            
            if items_count == 0 and items:
                current_page = 0
                continue
            
            self.print_commands_help()
            if self.selected_files:
                self.display_selected_files()
            
            # الحصول على الأمر
            command = input(f"\n{Colors.GREEN}💻 أدخل الأمر: {Colors.ENDC}").strip().lower()
            
            # معالجة الأوامر
            if command == 'q':
                print(f"{Colors.CYAN}👋 إلى اللقاء!{Colors.ENDC}")
                break
            
            elif command == 'r':
                current_page = 0
                continue
            
            elif command == 'h':
                self.current_path = os.path.expanduser("~")
                current_page = 0
                continue
            
            elif command == 'n':
                if current_page < total_pages - 1:
                    current_page += 1
                continue
            
            elif command == 'p':
                if current_page > 0:
                    current_page -= 1
                continue
            
            elif command == 'c':
                self.selected_files = []
                print(f"{Colors.GREEN}✅ تم مسح جميع المختارات!{Colors.ENDC}")
                await asyncio.sleep(1)
                continue
            
            elif command == 'a':
                # اختيار جميع الملفات
                files_only = [item for item in items if item['type'] == 'file']
                self.selected_files = files_only.copy()
                print(f"{Colors.GREEN}✅ تم اختيار {len(files_only)} ملف!{Colors.ENDC}")
                await asyncio.sleep(1)
                continue
            
            elif command == 'u':
                await self.upload_selected_files()
                continue
            
            elif command.startswith('s '):
                # اختيار/إلغاء اختيار ملف
                try:
                    file_num = int(command.split()[1])
                    start_idx = current_page * 15
                    actual_idx = file_num - 1
                    
                    if 0 <= actual_idx < len(items):
                        item = items[actual_idx]
                        if item['type'] == 'file':
                            # البحث في المختارات
                            existing = [f for f in self.selected_files if f['path'] == item['path']]
                            if existing:
                                self.selected_files = [f for f in self.selected_files if f['path'] != item['path']]
                                print(f"{Colors.GREEN}➖ تم إلغاء اختيار: {item['name']}{Colors.ENDC}")
                            else:
                                self.selected_files.append(item)
                                print(f"{Colors.GREEN}➕ تم اختيار: {item['name']}{Colors.ENDC}")
                            await asyncio.sleep(1)
                        else:
                            print(f"{Colors.FAIL}❌ يمكن اختيار الملفات فقط!{Colors.ENDC}")
                            await asyncio.sleep(1)
                    else:
                        print(f"{Colors.FAIL}❌ رقم غير صحيح!{Colors.ENDC}")
                        await asyncio.sleep(1)
                except (ValueError, IndexError):
                    print(f"{Colors.FAIL}❌ استخدم: s رقم_الملف{Colors.ENDC}")
                    await asyncio.sleep(1)
                continue
            
            elif command.startswith('/ '):
                # بحث
                self.search_query = command[2:].strip()
                print(f"{Colors.GREEN}🔍 البحث عن: '{self.search_query}'{Colors.ENDC}")
                current_page = 0
                await asyncio.sleep(1)
                continue
            
            elif command.startswith('f '):
                # تصفية
                filter_type = command[2:].strip()
                valid_filters = ['video', 'audio', 'image', 'document', 'archive', 'code']
                if filter_type in valid_filters:
                    self.filter_type = filter_type
                    print(f"{Colors.GREEN}🎯 التصفية حسب: {filter_type}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}❌ نوع تصفية غير صحيح! استخدم: {', '.join(valid_filters)}{Colors.ENDC}")
                current_page = 0
                await asyncio.sleep(1)
                continue
            
            elif command.startswith('o '):
                # ترتيب
                sort_type = command[2:].strip()
                valid_sorts = ['name', 'size', 'date']
                if sort_type in valid_sorts:
                    if self.sort_by == sort_type:
                        self.sort_reverse = not self.sort_reverse
                    else:
                        self.sort_by = sort_type
                        self.sort_reverse = False
                    print(f"{Colors.GREEN}📊 الترتيب حسب: {sort_type} {'(عكسي)' if self.sort_reverse else ''}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}❌ نوع ترتيب غير صحيح! استخدم: {', '.join(valid_sorts)}{Colors.ENDC}")
                current_page = 0
                await asyncio.sleep(1)
                continue
            
            elif command == 'b':
                # إدارة الإشارات المرجعية
                self.manage_bookmarks()
                current_page = 0
                continue
            
            elif command.startswith('i '):
                # عرض معلومات ملف
                try:
                    file_num = int(command.split()[1])
                    if 1 <= file_num <= len(items):
                        item = items[file_num - 1]
                        if item['type'] == 'file':
                            self.display_file_info(item['path'])
                        else:
                            print(f"{Colors.FAIL}❌ يمكن عرض معلومات الملفات فقط!{Colors.ENDC}")
                            await asyncio.sleep(1)
                    else:
                        print(f"{Colors.FAIL}❌ رقم غير صحيح!{Colors.ENDC}")
                        await asyncio.sleep(1)
                except (ValueError, IndexError):
                    print(f"{Colors.FAIL}❌ استخدم: i رقم_الملف{Colors.ENDC}")
                    await asyncio.sleep(1)
                continue
            
            elif command.isdigit():
                # فتح مجلد أو ملف
                try:
                    item_num = int(command)
                    if 1 <= item_num <= len(items):
                        selected_item = items[item_num - 1]
                        
                        if selected_item['type'] == 'parent':
                            self.current_path = selected_item['path']
                            current_page = 0
                        elif selected_item['type'] == 'folder':
                            self.current_path = selected_item['path']
                            current_page = 0
                        elif selected_item['type'] == 'file':
                            # اختيار الملف
                            if selected_item not in self.selected_files:
                                self.selected_files.append(selected_item)
                                print(f"{Colors.GREEN}✅ تم اختيار: {selected_item['name']}{Colors.ENDC}")
                            else:
                                print(f"{Colors.CYAN}ℹ️ الملف مختار مسبقاً: {selected_item['name']}{Colors.ENDC}")
                            await asyncio.sleep(1)
                    else:
                        print(f"{Colors.FAIL}❌ اختر رقم من 1 إلى {len(items)}{Colors.ENDC}")
                        await asyncio.sleep(1)
                except ValueError:
                    print(f"{Colors.FAIL}❌ أدخل رقم صحيح!{Colors.ENDC}")
                    await asyncio.sleep(1)
                continue
            
            else:
                print(f"{Colors.FAIL}❌ أمر غير مفهوم! استخدم 'h' لعرض المساعدة{Colors.ENDC}")
                await asyncio.sleep(1)

async def main():
    """الدالة الرئيسية"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"{Colors.FAIL}❌ يرجى تعديل BOT_TOKEN في الكود!{Colors.ENDC}")
        return
    
    uploader = TelegramVideoUploader(BOT_TOKEN)
    await uploader.run_interactive_explorer()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.CYAN}👋 تم إيقاف البرنامج!{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}❌ خطأ غير متوقع: {e}{Colors.ENDC}")
        logger.exception("خطأ في التشغيل:")
