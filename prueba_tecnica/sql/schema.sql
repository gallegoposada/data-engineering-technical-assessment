-- =====================================================================
-- Esquema de la base de datos (PostgreSQL 16)
--   1) raw_jobs : copia del CSV con los tipos correctos (listas y diccionarios incluidos)
--   2) 14 tablas del modelo normalizado (3FN)
-- Este script se ejecuta completo cada vez que corre el pipeline: primero borra
-- todo y luego crea de nuevo, así cada ejecución parte de cero (sin duplicar datos).
-- =====================================================================

-- ---------- Borrado (de las tablas hijas a las padres) ----------
DROP TABLE IF EXISTS skill_type_links CASCADE;
DROP TABLE IF EXISTS job_skills CASCADE;
DROP TABLE IF EXISTS job_schedules CASCADE;
DROP TABLE IF EXISTS job_salaries CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS skill_types CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS schedule_types CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS search_locations CASCADE;
DROP TABLE IF EXISTS countries CASCADE;
DROP TABLE IF EXISTS title_categories CASCADE;
DROP TABLE IF EXISTS platforms CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS raw_jobs CASCADE;

-- ---------- Fase 1: tabla con los datos tal cual vienen del CSV ----------
CREATE TABLE raw_jobs (
    raw_id                INTEGER PRIMARY KEY,   -- número de fila en el CSV
    job_title_short       TEXT,
    job_title             TEXT,
    job_location          TEXT,
    job_via               TEXT,
    job_schedule_type     TEXT,
    job_work_from_home    BOOLEAN,
    search_location       TEXT,
    job_posted_date       TIMESTAMP,
    job_no_degree_mention BOOLEAN,
    job_health_insurance  BOOLEAN,
    job_country           TEXT,
    salary_rate           TEXT,
    salary_year_avg       NUMERIC(12, 2),
    salary_hour_avg       NUMERIC(10, 2),
    company_name          TEXT,
    job_skills            TEXT[],                -- lista de skills como arreglo de PostgreSQL
    job_type_skills       JSONB                  -- diccionario {tipo: [skills]} como JSON
);

-- ---------- Fase 2: modelo normalizado (3FN) ----------
-- Catálogos: cada dato repetido vive una sola vez.
CREATE TABLE companies (
    company_id    INTEGER PRIMARY KEY,
    company_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE platforms (                -- job_via: LinkedIn, Indeed, ...
    platform_id    INTEGER PRIMARY KEY,
    platform_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE title_categories (         -- job_title_short: Data Engineer, Data Analyst, ...
    title_category_id    INTEGER PRIMARY KEY,
    title_category_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE countries (
    country_id    INTEGER PRIMARY KEY,
    country_name  TEXT NOT NULL UNIQUE
);

-- El país depende de la búsqueda que hizo el bot (search_location), no del lugar
-- del puesto, por eso country_id vive aquí. Es NULL en las pocas búsquedas sin país.
CREATE TABLE search_locations (
    search_location_id    INTEGER PRIMARY KEY,
    search_location_name  TEXT NOT NULL UNIQUE,
    country_id            INTEGER REFERENCES countries (country_id)
);

CREATE TABLE locations (                -- job_location tal como aparece en la oferta
    location_id    INTEGER PRIMARY KEY,
    location_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE schedule_types (           -- Full-time, Part-time, Contractor, ...
    schedule_type_id    INTEGER PRIMARY KEY,
    schedule_type_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE skills (
    skill_id    INTEGER PRIMARY KEY,
    skill_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE skill_types (              -- programming, cloud, databases, ...
    skill_type_id    INTEGER PRIMARY KEY,
    skill_type_name  TEXT NOT NULL UNIQUE
);

-- Tabla central: una fila por oferta de trabajo.
CREATE TABLE jobs (
    job_id                 INTEGER PRIMARY KEY,
    job_title              TEXT NOT NULL,
    title_category_id      INTEGER NOT NULL REFERENCES title_categories (title_category_id),
    company_id             INTEGER NOT NULL REFERENCES companies (company_id),
    platform_id            INTEGER NOT NULL REFERENCES platforms (platform_id),
    location_id            INTEGER REFERENCES locations (location_id),  -- NULL si la oferta no trae ubicación
    search_location_id     INTEGER NOT NULL REFERENCES search_locations (search_location_id),
    posted_at              TIMESTAMP NOT NULL,
    job_work_from_home     BOOLEAN NOT NULL,
    job_no_degree_mention  BOOLEAN NOT NULL,
    job_health_insurance   BOOLEAN NOT NULL
);

-- Salario: solo ~4% de las ofertas lo tiene, por eso va en su propia tabla (1 a 0..1).
CREATE TABLE job_salaries (
    job_id           INTEGER PRIMARY KEY REFERENCES jobs (job_id),
    salary_rate      TEXT NOT NULL CHECK (salary_rate IN ('year', 'hour')),
    salary_year_avg  NUMERIC(12, 2),
    salary_hour_avg  NUMERIC(10, 2),
    CHECK (
        (salary_rate = 'year' AND salary_year_avg IS NOT NULL AND salary_hour_avg IS NULL) OR
        (salary_rate = 'hour' AND salary_hour_avg IS NOT NULL AND salary_year_avg IS NULL)
    )
);

-- Tablas puente (relaciones muchos a muchos).
CREATE TABLE job_schedules (            -- una oferta puede tener varias jornadas
    job_id            INTEGER NOT NULL REFERENCES jobs (job_id),
    schedule_type_id  INTEGER NOT NULL REFERENCES schedule_types (schedule_type_id),
    PRIMARY KEY (job_id, schedule_type_id)
);

CREATE TABLE job_skills (               -- oferta <-> skill
    job_id    INTEGER NOT NULL REFERENCES jobs (job_id),
    skill_id  INTEGER NOT NULL REFERENCES skills (skill_id),
    PRIMARY KEY (job_id, skill_id)
);

CREATE TABLE skill_type_links (         -- skill <-> tipo (una skill puede tener varios tipos)
    skill_id       INTEGER NOT NULL REFERENCES skills (skill_id),
    skill_type_id  INTEGER NOT NULL REFERENCES skill_types (skill_type_id),
    PRIMARY KEY (skill_id, skill_type_id)
);

-- Índices para las búsquedas más comunes (las llaves primarias ya tienen el suyo).
CREATE INDEX ix_jobs_company ON jobs (company_id);
CREATE INDEX ix_jobs_title_category ON jobs (title_category_id);
CREATE INDEX ix_jobs_platform ON jobs (platform_id);
CREATE INDEX ix_jobs_location ON jobs (location_id);
CREATE INDEX ix_jobs_search_location ON jobs (search_location_id);
CREATE INDEX ix_jobs_posted_at ON jobs (posted_at);
CREATE INDEX ix_job_skills_skill ON job_skills (skill_id);
CREATE INDEX ix_job_schedules_type ON job_schedules (schedule_type_id);
