# -*- coding: utf-8 -*-
"""
Custom exceptions for GLR Gestione Locale Radioamatori

Provides specific exception types for better error handling
and more informative error messages.
"""


class LibroSociError(Exception):
    """Base exception for all GLR Gestione Locale Radioamatori errors."""
    pass


class DatabaseError(LibroSociError):
    """Exception raised for database-related errors."""
    
    def __init__(self, message: str, original_error: Exception | None = None):
        """
        Initialize database error.
        
        Args:
            message: Human-readable error message
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error
    
    def __str__(self):
        if self.original_error:
            return f"{self.args[0]} (Causa: {str(self.original_error)})"
        return self.args[0]


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails."""
    pass


class DatabaseIntegrityError(DatabaseError):
    """Exception raised when database integrity check fails."""
    pass


class DatabaseLockError(DatabaseError):
    """Exception raised when database is locked."""
    pass


class ValidationError(LibroSociError):
    """Exception raised when data validation fails."""
    
    def __init__(self, field: str, message: str):
        """
        Initialize validation error.
        
        Args:
            field: Field name that failed validation
            message: Human-readable error message
        """
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


class RequiredFieldError(ValidationError):
    """Exception raised when a required field is missing."""
    
    def __init__(self, field: str):
        super().__init__(field, "Campo obbligatorio")


class InvalidFormatError(ValidationError):
    """Exception raised when a field has invalid format."""
    pass


class BackupError(LibroSociError):
    """Exception raised for backup-related errors."""
    
    def __init__(self, message: str, backup_path: str | None = None):
        """
        Initialize backup error.
        
        Args:
            message: Human-readable error message
            backup_path: Path to backup file (if applicable)
        """
        super().__init__(message)
        self.backup_path = backup_path


class BackupIntegrityError(BackupError):
    """Exception raised when backup file is corrupted."""
    pass


class RestoreError(BackupError):
    """Exception raised when database restore fails."""
    pass


class ImportError(LibroSociError):
    """Exception raised during CSV import operations."""
    
    def __init__(self, message: str, row_number: int | None = None):
        """
        Initialize import error.
        
        Args:
            message: Human-readable error message
            row_number: Row number in CSV that caused the error
        """
        if row_number:
            message = f"Riga {row_number}: {message}"
        super().__init__(message)
        self.row_number = row_number


class ExportError(LibroSociError):
    """Exception raised during export operations."""
    pass


class DocumentError(LibroSociError):
    """Exception raised for document management errors."""
    
    def __init__(self, message: str, file_path: str | None = None):
        """
        Initialize document error.
        
        Args:
            message: Human-readable error message
            file_path: Path to document file (if applicable)
        """
        super().__init__(message)
        self.file_path = file_path


class ConfigurationError(LibroSociError):
    """Exception raised for configuration errors."""
    pass


# Exception mapping for common SQLite errors
def map_sqlite_exception(e: Exception) -> DatabaseError:
    """
    Map SQLite exceptions to custom DatabaseError types.
    
    Args:
        e: Original SQLite exception
    
    Returns:
        Appropriate DatabaseError subclass
    """
    import sqlite3
    
    error_msg = str(e).lower()
    
    if isinstance(e, sqlite3.IntegrityError):
        if "unique" in error_msg:
            return DatabaseIntegrityError(
                "Violazione vincolo univocità (record duplicato)",
                original_error=e
            )
        elif "foreign key" in error_msg:
            return DatabaseIntegrityError(
                "Violazione chiave esterna (riferimento non valido)",
                original_error=e
            )
        else:
            return DatabaseIntegrityError(
                "Violazione integrità database",
                original_error=e
            )
    
    elif isinstance(e, sqlite3.OperationalError):
        if "locked" in error_msg or "busy" in error_msg:
            return DatabaseLockError(
                "Database temporaneamente bloccato. Riprovare.",
                original_error=e
            )
        elif "unable to open" in error_msg or "disk" in error_msg:
            return DatabaseConnectionError(
                "Impossibile accedere al database. Verificare permessi e spazio su disco.",
                original_error=e
            )
        else:
            return DatabaseError(
                f"Errore operazione database: {str(e)}",
                original_error=e
            )
    
    elif isinstance(e, sqlite3.DatabaseError):
        return DatabaseError(
            f"Errore database: {str(e)}",
            original_error=e
        )
    
    else:
        return DatabaseError(
            f"Errore imprevisto: {str(e)}",
            original_error=e
        )
