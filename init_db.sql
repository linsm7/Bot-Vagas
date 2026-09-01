-- Gerado a partir de specs/001-bot-alertas-vagas/data-model.md §3.
-- Qualquer mudança de schema deve ser feita primeiro na spec, depois aqui (Artigo VIII).

CREATE TABLE vagas (
    id               BIGSERIAL PRIMARY KEY,
    hash_unico       CHAR(64)     NOT NULL,
    titulo           TEXT         NOT NULL,
    empresa          TEXT         NOT NULL,
    localizacao      TEXT         NOT NULL,
    modalidade       VARCHAR(20)  NOT NULL
                      CHECK (modalidade IN ('remoto', 'presencial', 'hibrido')),
    url              TEXT         NOT NULL,
    fonte            VARCHAR(50)  NOT NULL,
    descricao        TEXT,
    stack_detectada  TEXT[]       NOT NULL DEFAULT '{}',
    data_publicacao  DATE,
    data_coleta      TIMESTAMPTZ  NOT NULL,
    notificado_em    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_vagas_hash_unico UNIQUE (hash_unico)
);

CREATE INDEX idx_vagas_data_coleta ON vagas (data_coleta DESC);
CREATE INDEX idx_vagas_fonte       ON vagas (fonte);
