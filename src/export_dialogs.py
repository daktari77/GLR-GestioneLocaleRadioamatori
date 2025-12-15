# -*- coding: utf-8 -*-
"""
Export dialogs for GLR Gestione Locale Radioamatori v4.2a
Provides UI for member export and reports
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger("librosoci")

class ExportDialog:
    """Main export dialog - choose format and options"""
    
    def __init__(self, parent, members_list, config=None):
        """
        Initialize export dialog
        
        Args:
            parent: Parent window
            members_list: List of members to export
            config: Section configuration
        """
        self.parent = parent
        self.members_list = members_list
        self.config = config or {}
        self.result = None
        
        self.win = tk.Toplevel(parent)
        self.win.title("Esportazione soci")
        self.win.geometry("400x300")
        self.win.transient(parent)
        self.win.grab_set()
        
        self._build_ui()
    
    def _build_ui(self):
        """Build dialog UI"""
        frame = ttk.Frame(self.win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Scegli il formato di esportazione:", font=("Segoe UI", 11)).pack(anchor="w", pady=10)
        
        # Format selection
        format_frame = ttk.LabelFrame(frame, text="Formato")
        format_frame.pack(fill=tk.X, pady=10)
        
        self.format_var = tk.StringVar(value="html")
        
        ttk.Radiobutton(format_frame, text="HTML (documento formattato)", variable=self.format_var, value="html").pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(format_frame, text="CSV (foglio di calcolo)", variable=self.format_var, value="csv").pack(anchor="w", padx=10, pady=5)
        
        # Include options
        options_frame = ttk.LabelFrame(frame, text="Opzioni")
        options_frame.pack(fill=tk.X, pady=10)
        
        self.include_inactive = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Includi soci inattivi", variable=self.include_inactive).pack(anchor="w", padx=10, pady=5)
        
        self.include_deleted = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Includi soci eliminati", variable=self.include_deleted).pack(anchor="w", padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Esporta", command=self._export).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Annulla", command=self.win.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _export(self):
        """Execute export"""
        try:
            from export import ExportManager
            from database import fetch_all
            
            # Filter members
            filtered_members = self._filter_members()
            
            if not filtered_members:
                messagebox.showwarning("Esportazione", "Nessun socio da esportare.")
                return
            
            # Export
            manager = ExportManager()
            fmt = self.format_var.get()
            
            if fmt == "csv":
                path = manager.export_members_csv(filtered_members)
            else:  # html
                path = manager.export_members_html(filtered_members, self.config)
            
            if path:
                messagebox.showinfo("Esportazione", f"File salvato:\n{path}")
                import os
                if hasattr(os, 'startfile'):  # Windows
                    try:
                        os.startfile(str(path))
                    except:
                        pass
                self.win.destroy()
            else:
                messagebox.showerror("Esportazione", "Errore durante l'esportazione.")
        
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
            logger.error(f"Export failed: {e}", exc_info=True)
    
    def _filter_members(self):
        """Filter members based on options"""
        filtered = []
        
        for member in self.members_list:
            # Skip inactive if not included
            if not member.get("attivo") and not self.include_inactive.get():
                continue
            
            # Skip deleted if not included
            if member.get("deleted_at") and not self.include_deleted.get():
                continue
            
            filtered.append(member)
        
        return filtered


class ReportsDialog:
    """Dialog for generating reports"""
    
    def __init__(self, parent, members_list, config=None):
        """
        Initialize reports dialog
        
        Args:
            parent: Parent window
            members_list: List of members
            config: Section configuration
        """
        self.parent = parent
        self.members_list = members_list
        self.config = config or {}
        
        self.win = tk.Toplevel(parent)
        self.win.title("Report e statistiche")
        self.win.geometry("500x400")
        self.win.transient(parent)
        self.win.grab_set()
        
        self._build_ui()
    
    def _build_ui(self):
        """Build dialog UI"""
        frame = ttk.Frame(self.win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Genera rapporti statistici:", font=("Segoe UI", 11)).pack(anchor="w", pady=10)
        
        # Report buttons
        reports_frame = ttk.LabelFrame(frame, text="Report disponibili")
        reports_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Button(reports_frame, text="📊 Statistiche generali", command=self._show_statistics).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(reports_frame, text="💰 Analisi quote", command=self._show_quota_report).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(reports_frame, text="👥 Composizione CD", command=self._show_cd_report).pack(fill=tk.X, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Chiudi", command=self.win.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _show_statistics(self):
        """Show general statistics report"""
        try:
            from export import ReportGenerator
            
            gen = ReportGenerator()
            stats = gen.generate_statistics(self.members_list)
            
            msg = f"""STATISTICHE GENERALI
            
Totale soci: {stats['total_members']}
Soci attivi: {stats['active_members']}
Soci inattivi: {stats['inactive_members']}
Età media: {stats['avg_age']:.1f} anni

QUOTE:
Q0: {stats['quota_stats']['q0']}
Q1: {stats['quota_stats']['q1']}
Q2: {stats['quota_stats']['q2']}

RUOLI CD:
"""
            for role, count in sorted(stats['cd_roles'].items()):
                msg += f"{role}: {count}\n"
            
            msg += "\nPROVINCE:"
            for prov, count in sorted(stats['by_province'].items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"\n{prov}: {count}"
            
            messagebox.showinfo("Statistiche", msg)
        
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _show_quota_report(self):
        """Show quota analysis report"""
        try:
            from export import ReportGenerator
            
            gen = ReportGenerator()
            report = gen.generate_quota_report(self.members_list)
            
            msg = f"""ANALISI QUOTE

Q0: {len(report['q0_members'])} soci
{self._format_list(report['q0_members'])}

Q1: {len(report['q1_members'])} soci
{self._format_list(report['q1_members'])}

Q2: {len(report['q2_members'])} soci
{self._format_list(report['q2_members'])}

Senza quota: {len(report['no_quota'])} soci
{self._format_list(report['no_quota'])}
"""
            
            messagebox.showinfo("Analisi quote", msg)
        
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _show_cd_report(self):
        """Show CD composition report"""
        try:
            from export import ReportGenerator
            
            gen = ReportGenerator()
            report = gen.generate_cd_report(self.members_list, self.config)
            
            msg = f"""COMPOSIZIONE CONSIGLIO DIRETTIVO
{report['section']}

"""
            for role, members in report['members'].items():
                count = len(members)
                msg += f"{role}: {count}\n"
                for member in members[:3]:  # Show first 3
                    msg += f"  • {member}\n"
                if count > 3:
                    msg += f"  ... e {count - 3} altri\n"
                msg += "\n"
            
            messagebox.showinfo("Composizione CD", msg)
        
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _format_list(self, items, max_items=5):
        """Format list for display"""
        if not items:
            return "(nessuno)"
        
        display = "\n".join(f"  • {item}" for item in items[:max_items])
        if len(items) > max_items:
            display += f"\n  ... e {len(items) - max_items} altri"
        return display
