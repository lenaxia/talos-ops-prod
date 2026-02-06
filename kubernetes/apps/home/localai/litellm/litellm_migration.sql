-- Drop old indexes
DROP INDEX IF EXISTS "LiteLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key";
DROP INDEX IF EXISTS "LiteLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key";
DROP INDEX IF EXISTS "LiteLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key";

-- ALTER TABLE LiteLLM_DailyEndUserSpend
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "api_key" TEXT NOT NULL DEFAULT '';
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "api_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "cache_creation_input_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "cache_read_input_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "completion_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "custom_llm_provider" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "date" TEXT NOT NULL DEFAULT '';
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "end_user_id" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "failed_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "id" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "model" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "model_group" TEXT;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "prompt_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "successful_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyEndUserSpend" ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- ALTER TABLE LiteLLM_DailyOrganizationSpend
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "api_key" TEXT NOT NULL DEFAULT '';
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "api_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "cache_creation_input_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "cache_read_input_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "completion_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "custom_llm_provider" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "date" TEXT NOT NULL DEFAULT '';
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "failed_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "id" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "mcp_namespaced_tool_name" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "model" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "model_group" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "organization_id" TEXT;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "prompt_tokens" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "successful_requests" BIGINT NOT NULL DEFAULT 0;
ALTER TABLE "LiteLLM_DailyOrganizationSpend" ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- ALTER TABLE LiteLLM_DailyTagSpend
ALTER TABLE "LiteLLM_DailyTagSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- ALTER TABLE LiteLLM_DailyTeamSpend
ALTER TABLE "LiteLLM_DailyTeamSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- ALTER TABLE LiteLLM_DailyUserSpend
ALTER TABLE "LiteLLM_DailyUserSpend" ADD COLUMN IF NOT EXISTS "endpoint" TEXT;

-- ALTER TABLE LiteLLM_MCPServerTable
ALTER TABLE "LiteLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "allow_all_keys" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "LiteLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "authorization_url" TEXT;
ALTER TABLE "LiteLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "registration_url" TEXT;
ALTER TABLE "LiteLLM_MCPServerTable" ADD COLUMN IF NOT EXISTS "token_url" TEXT;

-- ALTER TABLE LiteLLM_ManagedFileTable
ALTER TABLE "LiteLLM_ManagedFileTable" ADD COLUMN IF NOT EXISTS "storage_backend" TEXT;
ALTER TABLE "LiteLLM_ManagedFileTable" ADD COLUMN IF NOT EXISTS "storage_url" TEXT;

-- ALTER TABLE LiteLLM_PromptTable
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "id" TEXT;
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "litellm_params" JSONB NOT NULL DEFAULT '{}';
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "prompt_id" TEXT;
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "prompt_info" JSONB;
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE "LiteLLM_PromptTable" ADD COLUMN IF NOT EXISTS "version" INTEGER NOT NULL DEFAULT 1;

-- ALTER TABLE LiteLLM_SpendLogs
ALTER TABLE "LiteLLM_SpendLogs" ADD COLUMN IF NOT EXISTS "agent_id" TEXT;

-- ALTER TABLE LiteLLM_TeamTable
ALTER TABLE "LiteLLM_TeamTable" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

-- ALTER TABLE LiteLLM_VerificationToken
ALTER TABLE "LiteLLM_VerificationToken" ADD COLUMN IF NOT EXISTS "router_settings" JSONB DEFAULT '{}';

-- CREATE TABLE LiteLLM_DeletedTeamTable
CREATE TABLE IF NOT EXISTS "LiteLLM_DeletedTeamTable" (
  "id" TEXT NOT NULL,
  "team_id" TEXT NOT NULL,
  "team_alias" TEXT,
  "organization_id" TEXT,
  "object_permission_id" TEXT,
  "admins" TEXT[],
  "members" TEXT[],
  "members_with_roles" JSONB NOT NULL DEFAULT '{}',
  "metadata" JSONB NOT NULL DEFAULT '{}',
  "max_budget" DOUBLE PRECISION,
  "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  "models" TEXT[],
  "max_parallel_requests" INTEGER,
  "tpm_limit" BIGINT,
  "rpm_limit" BIGINT,
  "budget_duration" TEXT,
  "budget_reset_at" TIMESTAMP(3),
  "blocked" BOOLEAN NOT NULL DEFAULT false,
  "model_spend" JSONB NOT NULL DEFAULT '{}',
  "model_max_budget" JSONB NOT NULL DEFAULT '{}',
  "router_settings" JSONB DEFAULT '{}',
  "team_member_permissions" TEXT[] DEFAULT ARRAY[]::TEXT[],
  "model_id" INTEGER,
  "created_at" TIMESTAMP(3),
  "updated_at" TIMESTAMP(3),
  "deleted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_by" TEXT,
  "deleted_by_api_key" TEXT,
  "litellm_changed_by" TEXT,
  CONSTRAINT "LiteLLM_DeletedTeamTable_pkey" PRIMARY KEY ("id")
);

-- CREATE TABLE LiteLLM_DeletedVerificationToken
CREATE TABLE IF NOT EXISTS "LiteLLM_DeletedVerificationToken" (
  "id" TEXT NOT NULL,
  "token" TEXT NOT NULL,
  "key_name" TEXT,
  "key_alias" TEXT,
  "soft_budget_cooldown" BOOLEAN NOT NULL DEFAULT false,
  "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  "expires" TIMESTAMP(3),
  "models" TEXT[],
  "aliases" JSONB NOT NULL DEFAULT '{}',
  "config" JSONB NOT NULL DEFAULT '{}',
  "user_id" TEXT,
  "team_id" TEXT,
  "permissions" JSONB NOT NULL DEFAULT '{}',
  "max_parallel_requests" INTEGER,
  "metadata" JSONB NOT NULL DEFAULT '{}',
  "blocked" BOOLEAN,
  "tpm_limit" BIGINT,
  "rpm_limit" BIGINT,
  "max_budget" DOUBLE PRECISION,
  "budget_duration" TEXT,
  "budget_reset_at" TIMESTAMP(3),
  "allowed_cache_controls" TEXT[] DEFAULT ARRAY[]::TEXT[],
  "allowed_routes" TEXT[] DEFAULT ARRAY[]::TEXT[],
  "model_spend" JSONB NOT NULL DEFAULT '{}',
  "model_max_budget" JSONB NOT NULL DEFAULT '{}',
  "router_settings" JSONB DEFAULT '{}',
  "budget_id" TEXT,
  "organization_id" TEXT,
  "object_permission_id" TEXT,
  "created_at" TIMESTAMP(3),
  "created_by" TEXT,
  "updated_at" TIMESTAMP(3),
  "updated_by" TEXT,
  "rotation_count" INTEGER DEFAULT 0,
  "auto_rotate" BOOLEAN DEFAULT false,
  "rotation_interval" TEXT,
  "last_rotation_at" TIMESTAMP(3),
  "key_rotation_at" TIMESTAMP(3),
  "deleted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_by" TEXT,
  "deleted_by_api_key" TEXT,
  "litellm_changed_by" TEXT,
  CONSTRAINT "LiteLLM_DeletedVerificationToken_pkey" PRIMARY KEY ("id")
);

-- CREATE TABLE LiteLLM_DailyAgentSpend
CREATE TABLE IF NOT EXISTS "LiteLLM_DailyAgentSpend" (
  "id" TEXT NOT NULL,
  "agent_id" TEXT,
  "date" TEXT NOT NULL,
  "api_key" TEXT NOT NULL,
  "model" TEXT,
  "model_group" TEXT,
  "custom_llm_provider" TEXT,
  "mcp_namespaced_tool_name" TEXT,
  "endpoint" TEXT,
  "prompt_tokens" BIGINT NOT NULL DEFAULT 0,
  "completion_tokens" BIGINT NOT NULL DEFAULT 0,
  "cache_read_input_tokens" BIGINT NOT NULL DEFAULT 0,
  "cache_creation_input_tokens" BIGINT NOT NULL DEFAULT 0,
  "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  "api_requests" BIGINT NOT NULL DEFAULT 0,
  "successful_requests" BIGINT NOT NULL DEFAULT 0,
  "failed_requests" BIGINT NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "LiteLLM_DailyAgentSpend_pkey" PRIMARY KEY ("id")
);

-- CREATE TABLE LiteLLM_UISettings
CREATE TABLE IF NOT EXISTS "LiteLLM_UISettings" (
  "id" TEXT NOT NULL DEFAULT 'ui_settings',
  "ui_settings" JSONB NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "LiteLLM_UISettings_pkey" PRIMARY KEY ("id")
);

-- CREATE TABLE LiteLLM_SkillsTable
CREATE TABLE IF NOT EXISTS "LiteLLM_SkillsTable" (
  "skill_id" TEXT NOT NULL,
  "display_title" TEXT,
  "description" TEXT,
  "instructions" TEXT,
  "source" TEXT NOT NULL DEFAULT 'custom',
  "latest_version" TEXT,
  "file_content" BYTEA,
  "file_name" TEXT,
  "file_type" TEXT,
  "metadata" JSONB DEFAULT '{}',
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_by" TEXT,
  "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_by" TEXT,
  CONSTRAINT "LiteLLM_SkillsTable_pkey" PRIMARY KEY ("skill_id")
);

-- Create indexes
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedTeamTable_team_id_idx" ON "LiteLLM_DeletedTeamTable"("team_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedTeamTable_deleted_at_idx" ON "LiteLLM_DeletedTeamTable"("deleted_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedTeamTable_organization_id_idx" ON "LiteLLM_DeletedTeamTable"("organization_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedTeamTable_team_alias_idx" ON "LiteLLM_DeletedTeamTable"("team_alias");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedTeamTable_created_at_idx" ON "LiteLLM_DeletedTeamTable"("created_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_token_idx" ON "LiteLLM_DeletedVerificationToken"("token");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_deleted_at_idx" ON "LiteLLM_DeletedVerificationToken"("deleted_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_user_id_idx" ON "LiteLLM_DeletedVerificationToken"("user_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_team_id_idx" ON "LiteLLM_DeletedVerificationToken"("team_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_organization_id_idx" ON "LiteLLM_DeletedVerificationToken"("organization_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_key_alias_idx" ON "LiteLLM_DeletedVerificationToken"("key_alias");
CREATE INDEX IF NOT EXISTS "LiteLLM_DeletedVerificationToken_created_at_idx" ON "LiteLLM_DeletedVerificationToken"("created_at");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_date_idx" ON "LiteLLM_DailyAgentSpend"("date");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_agent_id_idx" ON "LiteLLM_DailyAgentSpend"("agent_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_api_key_idx" ON "LiteLLM_DailyAgentSpend"("api_key");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_model_idx" ON "LiteLLM_DailyAgentSpend"("model");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_mcp_namespaced_tool_name_idx" ON "LiteLLM_DailyAgentSpend"("mcp_namespaced_tool_name");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_endpoint_idx" ON "LiteLLM_DailyAgentSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_agent_id_date_api_key_model_custom__key" ON "LiteLLM_DailyAgentSpend"("agent_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_date_idx" ON "LiteLLM_DailyEndUserSpend"("date");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_end_user_id_idx" ON "LiteLLM_DailyEndUserSpend"("end_user_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_api_key_idx" ON "LiteLLM_DailyEndUserSpend"("api_key");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_model_idx" ON "LiteLLM_DailyEndUserSpend"("model");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_mcp_namespaced_tool_name_idx" ON "LiteLLM_DailyEndUserSpend"("mcp_namespaced_tool_name");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_endpoint_idx" ON "LiteLLM_DailyEndUserSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_end_user_id_date_api_key_model_cu_key" ON "LiteLLM_DailyEndUserSpend"("end_user_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_date_idx" ON "LiteLLM_DailyOrganizationSpend"("date");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_organization_id_idx" ON "LiteLLM_DailyOrganizationSpend"("organization_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_api_key_idx" ON "LiteLLM_DailyOrganizationSpend"("api_key");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_model_idx" ON "LiteLLM_DailyOrganizationSpend"("model");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_mcp_namespaced_tool_name_idx" ON "LiteLLM_DailyOrganizationSpend"("mcp_namespaced_tool_name");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_endpoint_idx" ON "LiteLLM_DailyOrganizationSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_organization_id_date_api_key_key" ON "LiteLLM_DailyOrganizationSpend"("organization_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyTagSpend_endpoint_idx" ON "LiteLLM_DailyTagSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyTagSpend_tag_date_api_key_model_custom_llm_pro_key" ON "LiteLLM_DailyTagSpend"("tag", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyTeamSpend_endpoint_idx" ON "LiteLLM_DailyTeamSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyTeamSpend_team_id_date_api_key_model_custom_ll_key" ON "LiteLLM_DailyTeamSpend"("team_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_DailyUserSpend_endpoint_idx" ON "LiteLLM_DailyUserSpend"("endpoint");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_DailyUserSpend_user_id_date_api_key_model_custom_ll_key" ON "LiteLLM_DailyUserSpend"("user_id", "date", "api_key", "model", "custom_llm_provider", "mcp_namespaced_tool_name", "endpoint");
CREATE INDEX IF NOT EXISTS "LiteLLM_PromptTable_prompt_id_idx" ON "LiteLLM_PromptTable"("prompt_id");
CREATE UNIQUE INDEX IF NOT EXISTS "LiteLLM_PromptTable_prompt_id_version_key" ON "LiteLLM_PromptTable"("prompt_id", "version");
