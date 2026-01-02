# -*- coding: utf-8 -*-
"""
Statistics panel for member management
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger("librosoci")

class StatsPanel(ttk.Frame):
    """Panel displaying statistics about members."""
    
    def __init__(self, parent, **kwargs):
        """Initialize statistics panel."""
        super().__init__(parent, **kwargs)
        self._build_ui()
        self.refresh()
    
    def _build_ui(self):
        """Build the statistics UI."""
        try:
            from .styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.winfo_toplevel())
        except Exception:
            pass

        # Title
        title = ttk.Label(self, text="Statistiche soci", font=("Segoe UI", 11, "bold"))
        title.pack(pady=10)
        
        # Main frame with grid layout
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Row 1: Active/Inactive
        ttk.Label(main_frame, text="Totale soci:", font="AppNormal").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.label_total = ttk.Label(main_frame, text="0", font="AppBold")
        self.label_total.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Attivi:", font="AppNormal").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.label_active = ttk.Label(main_frame, text="0", font="AppBold", foreground="green")
        self.label_active.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Inattivi:", font="AppNormal").grid(row=0, column=4, sticky="w", padx=5, pady=5)
        self.label_inactive = ttk.Label(main_frame, text="0", font="AppBold", foreground="red")
        self.label_inactive.grid(row=0, column=5, sticky="w", padx=5, pady=5)
        
        # Row 2: Voting rights
        ttk.Label(main_frame, text="Diritto voto:", font="AppNormal").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.label_with_vote = ttk.Label(main_frame, text="0", font="AppBold", foreground="blue")
        self.label_with_vote.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="% Voto:", font="AppNormal").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.label_vote_pct = ttk.Label(main_frame, text="0%", font="AppBold")
        self.label_vote_pct.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        
        # Row 3: Privacy
        ttk.Label(main_frame, text="Privacy firmato:", font="AppNormal").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.label_privacy_signed = ttk.Label(main_frame, text="0", font="AppBold", foreground="green")
        self.label_privacy_signed.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Senza privacy:", font="AppNormal").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        self.label_no_privacy = ttk.Label(main_frame, text="0", font="AppBold", foreground="red")
        self.label_no_privacy.grid(row=2, column=3, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="% Privacy:", font="AppNormal").grid(row=2, column=4, sticky="w", padx=5, pady=5)
        self.label_privacy_pct = ttk.Label(main_frame, text="0%", font="AppBold")
        self.label_privacy_pct.grid(row=2, column=5, sticky="w", padx=5, pady=5)
        
        # Separator
        sep = ttk.Separator(main_frame, orient="horizontal")
        sep.grid(row=3, column=0, columnspan=6, sticky="ew", padx=5, pady=10)
        
        # Row 4: Documents
        ttk.Label(main_frame, text="Con documenti:", font="AppNormal").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.label_with_docs = ttk.Label(main_frame, text="0", font="AppBold")
        self.label_with_docs.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="% Documenti:", font="AppNormal").grid(row=4, column=2, sticky="w", padx=5, pady=5)
        self.label_docs_pct = ttk.Label(main_frame, text="0%", font="AppBold")
        self.label_docs_pct.grid(row=4, column=3, sticky="w", padx=5, pady=5)
        
        # Refresh button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Aggiorna", command=self.refresh).pack(side=tk.RIGHT)
    
    def refresh(self):
        """Refresh statistics from database."""
        try:
            from database import fetch_one

            # Normalize boolean-like columns before counting so strings like "Si" or "No"
            # coming from legacy imports are handled correctly.
            attivo_expr = "LOWER(TRIM(COALESCE(CAST(attivo AS TEXT), '')))"
            voto_expr = "LOWER(TRIM(COALESCE(CAST(voto AS TEXT), '')))"
            privacy_expr = "LOWER(TRIM(COALESCE(CAST(privacy_signed AS TEXT), '')))"
            truthy_values = "('1','true','si','sì','yes')"

            stats = fetch_one(
                f"""
                SELECT
                    COUNT(*) AS total_cnt,
                    SUM(CASE WHEN {attivo_expr} IN {truthy_values} THEN 1 ELSE 0 END) AS active_cnt,
                    SUM(CASE WHEN {attivo_expr} IN {truthy_values} THEN 0 ELSE 1 END) AS inactive_cnt,
                    SUM(CASE WHEN {voto_expr} IN {truthy_values} AND {attivo_expr} IN {truthy_values} THEN 1 ELSE 0 END) AS vote_cnt,
                    SUM(CASE WHEN {privacy_expr} IN {truthy_values} THEN 1 ELSE 0 END) AS privacy_yes_cnt,
                    SUM(CASE WHEN {privacy_expr} IN {truthy_values} THEN 0 ELSE 1 END) AS privacy_no_cnt
                FROM soci
                WHERE deleted_at IS NULL
                """
            )

            total_count = stats['total_cnt'] if stats else 0
            active_count = stats['active_cnt'] if stats else 0
            inactive_count = stats['inactive_cnt'] if stats else 0
            with_vote_count = stats['vote_cnt'] if stats else 0
            privacy_signed_count = stats['privacy_yes_cnt'] if stats else 0
            no_privacy_count = stats['privacy_no_cnt'] if stats else 0
            
            # Documents (soci with at least one document)
            with_docs = fetch_one("""
                SELECT COUNT(DISTINCT socio_id) as cnt FROM documenti
                WHERE socio_id IN (SELECT id FROM soci WHERE deleted_at IS NULL)
            """)
            with_docs_count = with_docs['cnt'] if with_docs else 0
            
            # Update labels
            self.label_total.config(text=str(total_count))
            self.label_active.config(text=str(active_count))
            self.label_inactive.config(text=str(inactive_count))
            self.label_with_vote.config(text=str(with_vote_count))
            self.label_privacy_signed.config(text=str(privacy_signed_count))
            self.label_no_privacy.config(text=str(no_privacy_count))
            self.label_with_docs.config(text=str(with_docs_count))
            
            # Calculate percentages
            if total_count > 0:
                vote_pct = int((with_vote_count / total_count) * 100)
                self.label_vote_pct.config(text=f"{vote_pct}%")
                
                privacy_pct = int((privacy_signed_count / total_count) * 100)
                self.label_privacy_pct.config(text=f"{privacy_pct}%")
                
                docs_pct = int((with_docs_count / total_count) * 100)
                self.label_docs_pct.config(text=f"{docs_pct}%")
            else:
                self.label_vote_pct.config(text="0%")
                self.label_privacy_pct.config(text="0%")
                self.label_docs_pct.config(text="0%")
            
        except Exception as e:
            logger.error("Failed to refresh stats: %s", e)
