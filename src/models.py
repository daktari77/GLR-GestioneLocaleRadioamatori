# -*- coding: utf-8 -*-
"""
Data models and validation for Libro Soci v4.2a

This module provides type-safe dataclasses with built-in validation
for member data, ensuring data integrity at the model level.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date, datetime
import re
import logging
from exceptions import ValidationError, RequiredFieldError, InvalidFormatError

logger = logging.getLogger("librosoci")


@dataclass
class Member:
    """
    Member (Socio) data model with built-in validation.
    
    All fields are validated on creation via __post_init__.
    Required fields: nome, cognome
    """
    
    # Identificazione
    id: Optional[int] = None
    matricola: Optional[str] = None
    
    # Dati anagrafici (required)
    nome: str = ""
    cognome: str = ""
    nominativo: Optional[str] = None
    nominativo2: Optional[str] = None
    
    # Dati nascita
    data_nascita: Optional[str] = None  # ISO format YYYY-MM-DD
    luogo_nascita: Optional[str] = None
    codicefiscale: Optional[str] = None
    
    # Contatti
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    
    # Status
    attivo: bool = True
    data_iscrizione: Optional[str] = None  # ISO format
    data_dimissioni: Optional[str] = None  # ISO format
    motivo_uscita: Optional[str] = None
    deleted_at: Optional[str] = None
    
    # Delibere
    delibera_numero: Optional[str] = None
    delibera_data: Optional[str] = None  # ISO format
    
    # Altri dati
    note: Optional[str] = None
    voto: bool = False
    familiare: Optional[str] = None
    cd_ruolo: Optional[str] = None
    socio: Optional[str] = None
    
    # Privacy
    privacy_ok: bool = False
    privacy_data: Optional[str] = None  # ISO format
    privacy_scadenza: Optional[str] = None  # ISO format
    privacy_signed: bool = False
    
    # Quote
    q0: Optional[str] = None
    q1: Optional[str] = None
    q2: Optional[str] = None
    
    def __post_init__(self):
        """Validate data after initialization."""
        self._validate_required_fields()
        self._validate_email()
        self._validate_codicefiscale()
        self._validate_cap()
        self._validate_provincia()
        self._validate_dates()
        self._validate_socio()
        self._validate_quota_codes()
    
    def _validate_required_fields(self):
        """Validate required fields are not empty."""
        if not self.nome or not self.nome.strip():
            raise RequiredFieldError("nome")
        
        if not self.cognome or not self.cognome.strip():
            raise RequiredFieldError("cognome")
        
        # Trim whitespace
        self.nome = self.nome.strip()
        self.cognome = self.cognome.strip()
    
    def _validate_email(self):
        """Validate email format if provided."""
        if self.email:
            email = self.email.strip()
            if not email:
                self.email = None
                return
            
            # RFC 5322 simplified pattern
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, email):
                raise InvalidFormatError("email", f"Formato non valido: {email}")
            
            self.email = email.lower()  # Normalize to lowercase
    
    def _validate_codicefiscale(self):
        """Validate Italian fiscal code format if provided."""
        if self.codicefiscale:
            cf = self.codicefiscale.strip().upper()
            if not cf:
                self.codicefiscale = None
                return
            
            # Italian CF: 16 alphanumeric characters
            if len(cf) != 16:
                raise InvalidFormatError("codicefiscale", f"Deve essere 16 caratteri: {cf}")
            
            if not cf.isalnum():
                raise InvalidFormatError("codicefiscale", f"Contiene caratteri non validi: {cf}")
            
            self.codicefiscale = cf
    
    def _validate_cap(self):
        """Validate Italian postal code format if provided."""
        if self.cap:
            cap = self.cap.strip()
            if not cap:
                self.cap = None
                return
            
            # Italian CAP: 5 digits
            if not cap.isdigit() or len(cap) != 5:
                raise InvalidFormatError("cap", f"Deve essere 5 cifre: {cap}")
            
            self.cap = cap
    
    def _validate_provincia(self):
        """Validate Italian province code if provided."""
        if self.provincia:
            prov = self.provincia.strip().upper()
            if not prov:
                self.provincia = None
                return
            
            # Province code: 2 uppercase letters
            if len(prov) != 2 or not prov.isalpha():
                raise InvalidFormatError("provincia", f"Deve essere 2 lettere: {prov}")
            
            self.provincia = prov

    def _validate_socio(self):
        """Validate socio membership type."""
        if self.socio is None:
            return
        socio = self.socio.strip().upper()
        if not socio:
            self.socio = None
            return

        allowed = {"HAM", "RCL", "THR"}
        if socio not in allowed:
            raise InvalidFormatError("socio", "Valori validi: HAM, RCL, THR")

        self.socio = socio
    
    def _validate_dates(self):
        """Validate date formats (ISO YYYY-MM-DD)."""
        date_fields = [
            ('data_nascita', self.data_nascita),
            ('data_iscrizione', self.data_iscrizione),
            ('data_dimissioni', self.data_dimissioni),
            ('delibera_data', self.delibera_data),
            ('privacy_data', self.privacy_data),
            ('privacy_scadenza', self.privacy_scadenza),
        ]
        
        for field_name, field_value in date_fields:
            if field_value:
                value = field_value.strip()
                if not value:
                    setattr(self, field_name, None)
                    continue
                
                # Validate ISO format
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                    raise InvalidFormatError(field_name, f"Formato data non valido (usa YYYY-MM-DD): {value}")
                
                # Validate date exists
                try:
                    year, month, day = map(int, value.split('-'))
                    date(year, month, day)
                except ValueError as e:
                    raise InvalidFormatError(field_name, f"Data non valida: {value}")
    
    def _validate_quota_codes(self):
        """Validate quota codes format (Q0/Q1/Q2)."""
        quota_pattern = re.compile(r'^[A-Z0-9]{2,3}$')
        
        for quota_field in ['q0', 'q1', 'q2']:
            quota_value = getattr(self, quota_field)
            if quota_value:
                quota = quota_value.strip().upper()
                if not quota:
                    setattr(self, quota_field, None)
                    continue
                
                if not quota_pattern.match(quota):
                    raise InvalidFormatError(quota_field, f"Formato non valido (2-3 caratteri alfanumerici maiuscoli): {quota}")
                
                setattr(self, quota_field, quota)
    
    def to_dict(self) -> dict:
        """
        Convert member to dictionary for database storage.
        
        Returns:
            Dictionary with all fields, excluding None id for new members
        """
        data = {
            'matricola': self.matricola,
            'nominativo': self.nominativo,
            'nominativo2': self.nominativo2,
            'nome': self.nome,
            'cognome': self.cognome,
            'data_nascita': self.data_nascita,
            'luogo_nascita': self.luogo_nascita,
            'codicefiscale': self.codicefiscale,
            'indirizzo': self.indirizzo,
            'cap': self.cap,
            'citta': self.citta,
            'provincia': self.provincia,
            'email': self.email,
            'telefono': self.telefono,
            'attivo': 1 if self.attivo else 0,
            'data_iscrizione': self.data_iscrizione,
            'data_dimissioni': self.data_dimissioni,
            'motivo_uscita': self.motivo_uscita,
            'delibera_numero': self.delibera_numero,
            'delibera_data': self.delibera_data,
            'note': self.note,
            'voto': 1 if self.voto else 0,
            'familiare': self.familiare,
            'cd_ruolo': self.cd_ruolo,
            'socio': self.socio,
            'privacy_ok': 1 if self.privacy_ok else 0,
            'privacy_data': self.privacy_data,
            'privacy_scadenza': self.privacy_scadenza,
            'privacy_signed': 1 if self.privacy_signed else 0,
            'q0': self.q0,
            'q1': self.q1,
            'q2': self.q2,
        }
        
        # Include ID only if exists (for updates)
        if self.id is not None:
            data['id'] = self.id
        
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Member':
        """
        Create Member instance from database row or dictionary.
        
        Args:
            data: Dictionary with member data (from DB or form)
        
        Returns:
            Member instance with validated data
        
        Raises:
            ValidationError: If validation fails
        """
        # Convert boolean fields from DB (0/1) to Python bool
        bool_fields = ['attivo', 'voto', 'privacy_ok', 'privacy_signed']
        for field in bool_fields:
            if field in data:
                value = data[field]
                if isinstance(value, (int, str)):
                    data[field] = str(value) in ('1', 'True', 'true', '1.0')
        
        # Filter only fields that exist in Member dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.cognome} {self.nome} (Mat. {self.matricola or 'N/A'})"


# Validation helper functions (for backward compatibility)

def validate_member_data(data: dict) -> Member:
    """
    Validate member data dictionary.
    
    Args:
        data: Dictionary with member data
    
    Returns:
        Validated Member instance
    
    Raises:
        ValidationError: If validation fails
    """
    return Member.from_dict(data)


def sanitize_member_input(raw_data: dict) -> dict:
    """
    Sanitize and normalize member input data.
    
    Args:
        raw_data: Raw input from form (strings)
    
    Returns:
        Normalized dictionary ready for Member creation
    """
    sanitized = {}
    
    for key, value in raw_data.items():
        # Skip None values
        if value is None:
            sanitized[key] = None
            continue
        
        # Trim strings
        if isinstance(value, str):
            value = value.strip()
            # Convert empty strings to None
            if not value:
                sanitized[key] = None
                continue
            
            # Normalize specific fields
            if key == 'email':
                value = value.lower()
            elif key in ('codicefiscale', 'provincia', 'q0', 'q1', 'q2', 'socio'):
                value = value.upper()
        
        sanitized[key] = value
    
    return sanitized
