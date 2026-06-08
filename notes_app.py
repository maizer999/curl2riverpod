#!/usr/bin/env python3
import sys
import json
import os
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QTextEdit, 
                             QPushButton, QLineEdit, QLabel, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QColor

class NotesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.notes_file = Path.home() / '.notes_app' / 'notes.json'
        self.notes_file.parent.mkdir(exist_ok=True)
        
        self.notes = {}
        self.current_note_id = None
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(2000)  # Auto-save every 2 seconds
        
        self.init_ui()
        self.load_notes()
        self.setWindowTitle('📝 Smart Notes')
        self.setGeometry(100, 100, 1200, 700)
        
    def init_ui(self):
        """Initialize the UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ===== LEFT PANEL =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QLabel('Notes')
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        left_layout.addWidget(title_label)
        
        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 Search notes...')
        self.search_input.textChanged.connect(self.filter_notes)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        left_layout.addWidget(self.search_input)
        
        # Notes list
        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_note)
        self.notes_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #007AFF;
                color: white;
            }
        """)
        left_layout.addWidget(self.notes_list)
        
        # Add note button
        self.add_btn = QPushButton('+ New Note')
        self.add_btn.clicked.connect(self.new_note)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0051D5;
            }
        """)
        left_layout.addWidget(self.add_btn)
        
        # ===== RIGHT PANEL =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(10)
        
        # Note title input
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText('Note Title...')
        self.title_input.textChanged.connect(self.mark_changed)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_input.setFont(title_font)
        self.title_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: none;
                border-bottom: 2px solid #007AFF;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        right_layout.addWidget(self.title_input)
        
        # Note content editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText('Start typing your note...')
        self.text_edit.textChanged.connect(self.mark_changed)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                font-family: 'Menlo', monospace;
            }
        """)
        right_layout.addWidget(self.text_edit)
        
        # Status label
        self.status_label = QLabel('Ready')
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        right_layout.addWidget(self.status_label)
        
        # ===== SPLITTER =====
        splitter = QSplitter(Qt.Horizontal)
        left_panel.setMaximumWidth(300)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
    def create_note(self, title='Untitled Note', content=''):
        """Create a new note record and make it the current note."""
        note_id = str(int(datetime.now().timestamp() * 1000))
        self.notes[note_id] = {
            'title': title,
            'content': content,
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat()
        }
        self.current_note_id = note_id
        self.save_notes()
        return note_id

    def new_note(self):
        """Create a new note and reset the editor for it."""
        self.create_note()
        self.title_input.setText('Untitled Note')
        self.text_edit.setText('')
        self.refresh_notes_list()
        self.title_input.setFocus()
        self.title_input.selectAll()
        
    def load_note(self, item):
        """Load selected note"""
        note_id = item.data(Qt.UserRole)
        if note_id in self.notes:
            self.current_note_id = note_id
            note = self.notes[note_id]
            self.title_input.blockSignals(True)
            self.text_edit.blockSignals(True)
            
            self.title_input.setText(note['title'])
            self.text_edit.setText(note['content'])
            
            self.title_input.blockSignals(False)
            self.text_edit.blockSignals(False)
            
            self.status_label.setText(f"Modified: {note['modified']}")
        
    def mark_changed(self):
        """Mark current note as changed"""
        # If the user starts typing without an active note, create one so
        # their text actually gets saved.
        if not self.current_note_id:
            if not (self.title_input.text() or self.text_edit.toPlainText()):
                return
            self.create_note()

        self.status_label.setText('Unsaved changes...')
        self.status_label.setStyleSheet("color: #FF9500; font-size: 12px; font-weight: bold;")
            
    def auto_save(self):
        """Auto-save current note"""
        if self.current_note_id and self.current_note_id in self.notes:
            self.notes[self.current_note_id]['title'] = self.title_input.text() or 'Untitled Note'
            self.notes[self.current_note_id]['content'] = self.text_edit.toPlainText()
            self.notes[self.current_note_id]['modified'] = datetime.now().isoformat()
            self.save_notes()
            
            if 'Unsaved' in self.status_label.text():
                self.status_label.setText('✓ Saved')
                self.status_label.setStyleSheet("color: #34C759; font-size: 12px; font-weight: bold;")
            
            self.refresh_notes_list()
        
    def filter_notes(self):
        """Filter notes by search query"""
        query = self.search_input.text().lower()
        
        for i in range(self.notes_list.count()):
            item = self.notes_list.item(i)
            note_id = item.data(Qt.UserRole)
            note = self.notes[note_id]
            
            matches = (query in note['title'].lower() or 
                      query in note['content'].lower())
            
            item.setHidden(not matches)
        
    def refresh_notes_list(self):
        """Refresh the notes list display"""
        current_query = self.search_input.text().lower()
        self.notes_list.clear()
        
        # Sort by modified date (newest first)
        sorted_notes = sorted(self.notes.items(), 
                            key=lambda x: x[1]['modified'], 
                            reverse=True)
        
        for note_id, note in sorted_notes:
            title = note['title'] or 'Untitled Note'
            content_preview = note['content'][:50].replace('\n', ' ')
            
            display_text = f"{title}\n{content_preview}..." if content_preview else title
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, note_id)
            
            # Highlight matching search results
            if current_query and (current_query in title.lower() or 
                                 current_query in note['content'].lower()):
                item.setForeground(QColor('#007AFF'))
            
            self.notes_list.addItem(item)
            
            # Select if it's the current note
            if note_id == self.current_note_id:
                self.notes_list.setCurrentItem(item)
        
    def load_notes(self):
        """Load notes from file"""
        if self.notes_file.exists():
            try:
                with open(self.notes_file, 'r') as f:
                    self.notes = json.load(f)
                self.refresh_notes_list()
                
                if self.notes:
                    # Load first note
                    first_note_id = list(self.notes.keys())[0]
                    item = self.notes_list.item(0)
                    if item:
                        self.load_note(item)
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to load notes: {e}')
        
    def save_notes(self):
        """Save notes to file"""
        try:
            with open(self.notes_file, 'w') as f:
                json.dump(self.notes, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save notes: {e}')
    
    def closeEvent(self, event):
        """Save on close"""
        self.auto_save()
        self.save_notes()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = NotesApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
