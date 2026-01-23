# -*- coding: utf-8 -*-
"""
Wizard di configurazione GLR con Flet
"""

import flet as ft
import json
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from config import CONFIG_JSON


# --- Wizard State Object ---
class WizardState:
    def __init__(self, section_data=None, import_result=None, cd_config=None, thunderbird=None, completed=False):
        self.section_data = section_data or {}
        self.import_result = import_result
        self.cd_config = cd_config or {}
        self.thunderbird = thunderbird or {}
        self.completed = completed


# --- Base Step Class ---
class WizardStep:
    def __init__(self, wizard, wizard_state: WizardState):
        self.wizard = wizard
        self.wizard_state = wizard_state

    def build(self) -> ft.Container:
        """Build the step UI"""
        raise NotImplementedError

    def on_next(self) -> bool:
        """Validate and proceed to next step"""
        return True

    def on_back(self) -> bool:
        """Handle back navigation"""
        return True

    def on_skip(self) -> bool:
        """Handle skip action"""
        return True


# --- Step 1: Welcome ---
class WelcomeStep(WizardStep):
    def build(self) -> ft.Container:
        admin_note = ""
        if self.wizard.mode == "ADMIN":
            admin_note = "\n\nStai operando in modalità amministratore."

        return ft.Container(
            content=ft.Column([
                ft.Text("Benvenuto in GLR", size=24, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Questa procedura guidata ti accompagnerà nella configurazione iniziale del gestionale GLR.\n\n"
                    "Nei prossimi passaggi potrai:\n"
                    "• inserire i dati della sezione\n"
                    "• importare l'elenco soci\n"
                    "• configurare il consiglio direttivo\n"
                    "• impostare eventuali integrazioni opzionali\n\n"
                    "La configurazione richiede solo pochi minuti e potrà essere modificata in seguito dall'area amministrativa." +
                    admin_note,
                    size=14
                ),
            ], spacing=20),
            padding=20
        )


# --- Step 2: Section Data ---
class SectionDataStep(WizardStep):
    def __init__(self, wizard, wizard_state: WizardState):
        super().__init__(wizard, wizard_state)
        self.fields = {}

    def build(self) -> ft.Container:
        # Pre-fill fields in ADMIN mode
        initial_values = {}
        if self.wizard.mode == "ADMIN":
            # Load existing config
            try:
                config_path = Path(CONFIG_JSON)
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        initial_values = {
                            'nome_sezione': config.get('nome_sezione', ''),
                            'codice_sezione': config.get('codice_sezione', ''),
                            'sede_operativa': config.get('sede_operativa', ''),
                            'sede_legale': config.get('sede_legale', ''),
                            'indirizzo_postale': config.get('indirizzo_postale', ''),
                            'email': config.get('email', ''),
                            'telefono': config.get('telefono', ''),
                            'sito_web': config.get('sito_web', ''),
                            'coordinate_bancarie': config.get('coordinate_bancarie', ''),
                            'recapiti': config.get('recapiti', ''),
                            'mandato': config.get('mandato', ''),
                        }
            except Exception:
                pass

        self.fields = {
            'nome_sezione': ft.TextField(label="Nome sezione", value=initial_values.get('nome_sezione', '')),
            'codice_sezione': ft.TextField(label="Codice sezione", value=initial_values.get('codice_sezione', '')),
            'sede_operativa': ft.TextField(label="Sede operativa", multiline=True, value=initial_values.get('sede_operativa', '')),
            'sede_legale': ft.TextField(label="Sede legale", multiline=True, value=initial_values.get('sede_legale', '')),
            'indirizzo_postale': ft.TextField(label="Indirizzo postale", multiline=True, value=initial_values.get('indirizzo_postale', '')),
            'email': ft.TextField(label="Indirizzo email", value=initial_values.get('email', '')),
            'telefono': ft.TextField(label="Telefono", value=initial_values.get('telefono', '')),
            'sito_web': ft.TextField(label="Sito web", value=initial_values.get('sito_web', '')),
            'coordinate_bancarie': ft.TextField(label="Coordinate bancarie", multiline=True, value=initial_values.get('coordinate_bancarie', '')),
            'recapiti': ft.TextField(label="Recapiti di sezione", multiline=True, value=initial_values.get('recapiti', '')),
            'mandato': ft.TextField(label="Mandato (formato: Mandato aaaa-aaaa)", value=initial_values.get('mandato', '')),
        }

        return ft.Container(
            content=ft.Column([
                ft.Text("Dati della sezione", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                *[field for field in self.fields.values()],
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
            padding=20
        )

    def on_next(self) -> bool:
        # Save to state
        self.wizard_state.section_data = {k: v.value for k, v in self.fields.items()}
        return True


# --- Step 3: Import Soci ---
class ImportSociStep(WizardStep):
    def __init__(self, wizard, wizard_state: WizardState):
        super().__init__(wizard, wizard_state)
        self.file_picker = None
        self.selected_file = None
        self.import_result = None

    def build(self) -> ft.Container:
        def pick_file(e):
            def on_file_selected(e: ft.FilePickerResultEvent):
                if e.files:
                    self.selected_file = e.files[0].path
                    file_text.value = f"File selezionato: {Path(self.selected_file).name}"
                    self.wizard.page.update()

            file_picker = ft.FilePicker(on_result=on_file_selected)
            self.wizard.page.overlay.append(file_picker)
            file_picker.pick_files(allowed_extensions=["csv"])

        def import_soci(e):
            if self.selected_file:
                # Use existing import logic
                try:
                    from import_soci_csv import import_soci_csv
                    result = import_soci_csv(self.selected_file)
                    self.import_result = result
                    result_text.value = f"Importati {len(result.get('imported', []))} soci. Errori: {len(result.get('errors', []))}"
                    self.wizard.page.update()
                except Exception as ex:
                    result_text.value = f"Errore importazione: {str(ex)}"
                    self.wizard.page.update()

        file_text = ft.Text("Nessun file selezionato")
        result_text = ft.Text("")

        return ft.Container(
            content=ft.Column([
                ft.Text("Importazione soci da CSV", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.ElevatedButton("Seleziona file CSV", on_click=pick_file),
                file_text,
                ft.ElevatedButton("Importa soci", on_click=import_soci),
                result_text,
            ], spacing=10),
            padding=20
        )

    def on_next(self) -> bool:
        self.wizard_state.import_result = self.import_result
        return True


# --- Step 4: Consiglio Direttivo ---
class CdStep(WizardStep):
    def build(self) -> ft.Container:
        content = [
            ft.Text("Consiglio direttivo", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=20),
        ]

        if self.wizard_state.import_result and self.wizard_state.import_result.get('imported'):
            content.append(ft.Text("Seleziona i soci per le cariche del consiglio direttivo"))
            # TODO: Implement member selection for CD roles
            content.append(ft.Text("Funzionalità da implementare: selezione soci per cariche"))
        else:
            content.append(ft.Text("Nessun socio importato. Puoi configurare il consiglio direttivo dopo l'importazione."))

        return ft.Container(
            content=ft.Column(content, spacing=10),
            padding=20
        )

    def on_next(self) -> bool:
        # Save CD config to state
        self.wizard_state.cd_config = {}  # Placeholder
        return True


# --- Step 5: Thunderbird ---
class ThunderbirdStep(WizardStep):
    def __init__(self, wizard, wizard_state: WizardState):
        super().__init__(wizard, wizard_state)
        self.thunderbird_path = ft.TextField(label="Percorso Thunderbird", value="data/tools/thunderbird")

    def build(self) -> ft.Container:
        def download_thunderbird(e):
            # Placeholder for download logic
            pass

        return ft.Container(
            content=ft.Column([
                ft.Text("Configurazione Thunderbird Portable", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.Text("Thunderbird Portable può essere integrato per funzionalità avanzate."),
                ft.Checkbox(label="Scarica Thunderbird Portable", value=False),
                self.thunderbird_path,
                ft.ElevatedButton("Scarica", on_click=download_thunderbird),
            ], spacing=10),
            padding=20
        )

    def on_next(self) -> bool:
        self.wizard_state.thunderbird = {
            'path': self.thunderbird_path.value,
            'auto_download': False  # Placeholder
        }
        return True


# --- Step 6: Summary ---
class SummaryStep(WizardStep):
    def build(self) -> ft.Container:
        summary = []

        # Section data
        summary.append(ft.Text("Dati sezione:", weight=ft.FontWeight.BOLD))
        for k, v in self.wizard_state.section_data.items():
            summary.append(ft.Text(f"{k}: {v}"))

        # Import result
        summary.append(ft.Container(height=20))
        summary.append(ft.Text("Importazione soci:", weight=ft.FontWeight.BOLD))
        if self.wizard_state.import_result:
            imported = len(self.wizard_state.import_result.get('imported', []))
            errors = len(self.wizard_state.import_result.get('errors', []))
            summary.append(ft.Text(f"Soci importati: {imported}, Errori: {errors}"))
        else:
            summary.append(ft.Text("Nessuna importazione effettuata"))

        # CD config
        summary.append(ft.Container(height=20))
        summary.append(ft.Text("Consiglio direttivo:", weight=ft.FontWeight.BOLD))
        summary.append(ft.Text("Da implementare"))

        # Thunderbird
        summary.append(ft.Container(height=20))
        summary.append(ft.Text("Thunderbird:", weight=ft.FontWeight.BOLD))
        summary.append(ft.Text(f"Percorso: {self.wizard_state.thunderbird.get('path', 'N/A')}"))

        return ft.Container(
            content=ft.Column([
                ft.Text("Riepilogo configurazione", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.Column(summary, spacing=5, scroll=ft.ScrollMode.AUTO),
            ], spacing=10),
            padding=20
        )


# --- Main Wizard Class ---
class GLRWizard:
    def __init__(self, mode: str = "FIRST_RUN", on_complete: Optional[Callable] = None):
        self.mode = mode.upper()
        self.on_complete = on_complete
        self.wizard_state = WizardState()
        self.current_step = 0

        # Pre-fill in ADMIN mode
        if self.mode == "ADMIN":
            self._load_existing_config()

        self.step_classes = [
            WelcomeStep,
            SectionDataStep,
            ImportSociStep,
            CdStep,
            ThunderbirdStep,
            SummaryStep,
        ]
        self.steps = []

    def _load_existing_config(self):
        try:
            config_path = Path(CONFIG_JSON)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.wizard_state.section_data = config
        except Exception:
            pass

    def build(self, page: ft.Page):
        self.page = page
        page.title = f"Configurazione GLR - {'Amministratore' if self.mode == 'ADMIN' else 'Prima esecuzione'}"
        page.theme_mode = ft.ThemeMode.LIGHT

        # Navigation buttons
        self.prev_btn = ft.ElevatedButton("Indietro", on_click=self._prev_step, disabled=True)
        self.next_btn = ft.ElevatedButton("Avanti", on_click=self._next_step)
        self.skip_btn = ft.ElevatedButton("Salta", on_click=self._skip_step)
        self.cancel_btn = ft.ElevatedButton("Annulla", on_click=self._cancel)
        self.save_btn = ft.ElevatedButton("Salva", on_click=self._save, visible=False)

        # Step indicator
        self.step_indicator = ft.Text(f"Passo {self.current_step + 1} di {len(self.step_classes)}")

        # Main content
        self.step_container = ft.Container()

        self._show_step(0)

        page.add(
            ft.Column([
                ft.Container(height=10),
                self.step_indicator,
                ft.Divider(),
                self.step_container,
                ft.Divider(),
                ft.Row([
                    self.prev_btn,
                    self.skip_btn,
                    self.next_btn,
                    self.cancel_btn,
                    self.save_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], expand=True)
        )

    def _show_step(self, step_idx: int):
        self.current_step = step_idx
        self.step_indicator.value = f"Passo {self.current_step + 1} di {len(self.step_classes)}"

        if step_idx < len(self.step_classes):
            step_class = self.step_classes[step_idx]
            step_instance = step_class(self, self.wizard_state)
            self.step_container.content = step_instance.build()
            self.steps.append(step_instance)

            # Update navigation
            self.prev_btn.disabled = step_idx == 0
            self.skip_btn.visible = hasattr(step_instance, 'on_skip') and step_idx == 2  # Import step
            self.next_btn.visible = step_idx < len(self.step_classes) - 1
            self.save_btn.visible = step_idx == len(self.step_classes) - 1

        self.page.update()

    def _next_step(self, e):
        if self.steps and self.steps[-1].on_next():
            if self.current_step < len(self.step_classes) - 1:
                self._show_step(self.current_step + 1)

    def _prev_step(self, e):
        if self.steps and self.steps[-1].on_back():
            if self.current_step > 0:
                self._show_step(self.current_step - 1)

    def _skip_step(self, e):
        if self.steps and self.steps[-1].on_skip():
            self._next_step(e)

    def _cancel(self, e):
        if self.mode == "FIRST_RUN":
            # Ask confirmation
            def confirm_cancel(e):
                self.page.window_destroy()
            dlg = ft.AlertDialog(
                title=ft.Text("Annulla configurazione"),
                content=ft.Text("Annullare la configurazione? I dati inseriti andranno persi."),
                actions=[
                    ft.TextButton("Sì", on_click=confirm_cancel),
                    ft.TextButton("No"),
                ]
            )
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
        else:
            self.page.window_destroy()

    def _save(self, e):
        # Save configuration
        config = self.wizard_state.section_data.copy()

        if self.wizard_state.import_result:
            config['import_result'] = self.wizard_state.import_result

        if self.wizard_state.cd_config:
            config['cd_config'] = self.wizard_state.cd_config

        if self.wizard_state.thunderbird:
            config['thunderbird'] = self.wizard_state.thunderbird

        # Save to file
        config_path = Path(CONFIG_JSON)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Set completed flag only in FIRST_RUN mode
        if self.mode == "FIRST_RUN":
            config['wizard_completed'] = True
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        if self.on_complete:
            self.on_complete(self.wizard_state)

        self.page.window_destroy()


def run_wizard(mode: str = "FIRST_RUN", on_complete: Optional[Callable] = None):
    """Run the GLR configuration wizard"""
    def main(page: ft.Page):
        wizard = GLRWizard(mode=mode, on_complete=on_complete)
        wizard.build(page)

    ft.app(target=main)


if __name__ == "__main__":
    run_wizard()