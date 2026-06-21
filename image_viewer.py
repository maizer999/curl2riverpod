import os
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image, ImageTk

class ImageExtensionViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Image Viewer")
        
        # Configure windowed mode
        self.root.geometry("1000x700")
        self.root.configure(bg='black')
        
        # Key bindings
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        
        # Setup image paths (all_images is the full set; image_paths is the filtered view)
        self.all_images = self.get_images()
        self.image_paths = list(self.all_images)
        self.current_index = 0

        # UI Setup
        self.setup_ui()

        # Load first image
        if self.image_paths:
            self.show_image()
        else:
            self.image_label.config(text="No images found in Desktop or Downloads.", fg="white")
            self.hide_buttons()

    def get_images(self):
        """Recursively scans Desktop and Downloads for common image formats."""
        extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        home = Path.home()
        search_dirs = [home / "Desktop", home / "Downloads"]

        found_images = []
        for directory in search_dirs:
            if directory.exists():
                for file in directory.rglob("*"):
                    if file.is_file() and file.suffix.lower() in extensions:
                        found_images.append(str(file))
        return sorted(found_images)

    def apply_search(self, *_):
        """Filters the loaded images by the text typed in the search box."""
        query = self.search_var.get().strip().lower()
        if query:
            self.image_paths = [p for p in self.all_images if query in os.path.basename(p).lower()]
        else:
            self.image_paths = list(self.all_images)

        self.current_index = 0
        if self.image_paths:
            self.show_buttons()
            self.show_image()
        else:
            self.image_label.config(image='', text="No images match your search.", fg="white")
            self.path_label.config(text="")
            self.hide_buttons()

    def setup_ui(self):
        """Creates the layout."""
        # Search bar at the very top to filter images by filename
        self.search_frame = tk.Frame(self.root, bg='black')
        self.search_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))

        tk.Label(self.search_frame, text="🔍 Search:", bg='black', fg='white', font=('Arial', 12)).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.apply_search)
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, font=('Arial', 12),
                                     bg='#222222', fg='white', insertbackground='white', relief='flat')
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, ipady=4)

        # Path label showing the current image's full path
        self.path_label = tk.Label(self.root, bg='black', fg='white', font=('Arial', 11), anchor='w', wraplength=980, justify='left')
        self.path_label.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Main display area for the image
        self.image_label = tk.Label(self.root, bg='black')
        self.image_label.pack(expand=True, fill=tk.BOTH)
        
        # Control panel at the bottom
        self.control_frame = tk.Frame(self.root, bg='black')
        self.control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        # Styled Buttons
        btn_style = {'font': ('Arial', 14), 'bg': '#333333', 'fg': 'white', 'padx': 20, 'pady': 10, 'borderwidth': 0}
        
        self.btn_prev = tk.Button(self.control_frame, text="◀ Previous", command=self.prev_image, **btn_style)
        self.btn_prev.pack(side=tk.LEFT, padx=50)
        
        self.btn_delete = tk.Button(self.control_frame, text="🗑 Delete", command=self.delete_image, fg="#ff4d4d", bg='#333333', font=('Arial', 14, 'bold'), padx=20, pady=10, borderwidth=0)
        self.btn_delete.pack(side=tk.LEFT, expand=True)
        
        self.btn_next = tk.Button(self.control_frame, text="Next ▶", command=self.next_image, **btn_style)
        self.btn_next.pack(side=tk.RIGHT, padx=50)
        
        # Exit instruction overlay
        self.exit_label = tk.Label(self.root, text="Press 'Esc' to Exit Fullscreen", font=('Arial', 10), fg='gray', bg='black')
        self.exit_label.place(x=10, y=10)

    def show_image(self):
        """Resizes and displays the current image."""
        if not self.image_paths:
            self.image_label.config(image='', text="No images left.", fg="white")
            self.path_label.config(text="")
            self.hide_buttons()
            return
            
        img_path = self.image_paths[self.current_index]
        self.path_label.config(text=img_path)

        try:
            # Update screen geometry to catch exact window dimensions
            self.root.update_idletasks()
            screen_width = self.root.winfo_width()
            screen_height = self.root.winfo_height() - 100 # Leave room for buttons
            
            # Load and resize image while maintaining aspect ratio
            img = Image.open(img_path)
            img_width, img_height = img.size
            
            ratio = min(screen_width / img_width, screen_height / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            # Prevent resizing to 0 width/height
            if new_width > 0 and new_height > 0:
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage and display
            self.tk_img = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.tk_img, text="")
        except Exception as e:
            self.image_label.config(text=f"Error loading image:\n{os.path.basename(img_path)}", fg="red")

    def next_image(self):
        if self.image_paths:
            self.current_index = (self.current_index + 1) % len(self.image_paths)
            self.show_image()

    def prev_image(self):
        if self.image_paths:
            self.current_index = (self.current_index - 1) % len(self.image_paths)
            self.show_image()

    def delete_image(self):
        if not self.image_paths:
            return
            
        current_file = self.image_paths[self.current_index]

        try:
            os.remove(current_file)
            del self.image_paths[self.current_index]
            if current_file in self.all_images:
                self.all_images.remove(current_file)

            # Adjust index after deletion
            if self.current_index >= len(self.image_paths):
                self.current_index = 0

            self.show_image()
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {e}")

    def hide_buttons(self):
        self.btn_prev.pack_forget()
        self.btn_next.pack_forget()
        self.btn_delete.pack_forget()

    def show_buttons(self):
        self.btn_prev.pack(side=tk.LEFT, padx=50)
        self.btn_delete.pack(side=tk.LEFT, expand=True)
        self.btn_next.pack(side=tk.RIGHT, padx=50)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageExtensionViewer(root)
    root.mainloop()