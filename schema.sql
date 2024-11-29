CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    prioridad TEXT NOT NULL,
    estado TEXT DEFAULT 'pendiente',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_creador TEXT NOT NULL,
    notas TEXT,
    archivo TEXT
);
