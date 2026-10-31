-- CIRDC-Pro empty schema, version 4. Select your database before importing.
-- DDL only: no addresses, accounts, credentials, or business records.
-- Run cirdc db-init after import to initialize application identity metadata.

CREATE TABLE IF NOT EXISTS schema_migrations (
        version INT PRIMARY KEY, applied_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS venues (
        kind VARCHAR(20) NOT NULL, number VARCHAR(64) NOT NULL, data LONGTEXT NOT NULL,
        PRIMARY KEY(kind,number)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS papers (
        number VARCHAR(64) PRIMARY KEY, data LONGTEXT NOT NULL,
        abstract_state VARCHAR(24) NOT NULL, keywords_state VARCHAR(24) NOT NULL,
        updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX field_coverage(abstract_state,keywords_state,number)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS paper_files (
        path VARCHAR(512) NOT NULL, number VARCHAR(64) NOT NULL, ordinal INT NOT NULL,
        PRIMARY KEY(path,number), INDEX by_number(number)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS manifests (
        path VARCHAR(512) PRIMARY KEY, digest CHAR(64) NOT NULL,
        checked_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sync_cursors (
        path VARCHAR(512) PRIMARY KEY, source_count INT NOT NULL,
        checked_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS runs (
        id CHAR(32) PRIMARY KEY, status VARCHAR(24) NOT NULL, params LONGTEXT NOT NULL,
        stats LONGTEXT NOT NULL, error LONGTEXT, pid INT,
        heartbeat TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tasks (
        id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id CHAR(32) NOT NULL,
        kind VARCHAR(24) NOT NULL, task_key VARCHAR(512) NOT NULL,
        payload LONGTEXT NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'pending',
        attempts INT NOT NULL DEFAULT 0, error LONGTEXT,
        UNIQUE KEY unique_task(run_id,kind,task_key), INDEX task_queue(run_id,status,id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exports (
        id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id CHAR(32) NOT NULL,
        path VARCHAR(512) NOT NULL, staged_path TEXT NOT NULL, digest CHAR(64) NOT NULL,
        status VARCHAR(24) NOT NULL DEFAULT 'pending', error LONGTEXT,
        UNIQUE KEY unique_export(run_id,path)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cirdc_identity (
    singleton TINYINT PRIMARY KEY, application VARCHAR(64) NOT NULL,
    schema_version INT NOT NULL, instance_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_instance(instance_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
