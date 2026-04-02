import { InitData } from '@supabase/mcp-utils';
import { z } from 'zod/v4';

type SuccessResponse = {
    success: true;
};
declare const storageBucketSchema: z.ZodObject<{
    id: z.ZodString;
    name: z.ZodString;
    owner: z.ZodString;
    created_at: z.ZodString;
    updated_at: z.ZodString;
    public: z.ZodBoolean;
}, z.core.$strip>;
declare const storageConfigSchema: z.ZodObject<{
    fileSizeLimit: z.ZodNumber;
    features: z.ZodObject<{
        imageTransformation: z.ZodObject<{
            enabled: z.ZodBoolean;
        }, z.core.$strip>;
        s3Protocol: z.ZodObject<{
            enabled: z.ZodBoolean;
        }, z.core.$strip>;
    }, z.core.$strip>;
}, z.core.$strip>;
declare const organizationSchema: z.ZodObject<{
    id: z.ZodString;
    name: z.ZodString;
    plan: z.ZodOptional<z.ZodString>;
    allowed_release_channels: z.ZodArray<z.ZodString>;
    opt_in_tags: z.ZodArray<z.ZodString>;
}, z.core.$strip>;
declare const projectSchema: z.ZodObject<{
    id: z.ZodString;
    organization_id: z.ZodString;
    name: z.ZodString;
    status: z.ZodString;
    created_at: z.ZodString;
    region: z.ZodString;
}, z.core.$strip>;
declare const branchSchema: z.ZodObject<{
    id: z.ZodString;
    name: z.ZodString;
    project_ref: z.ZodString;
    parent_project_ref: z.ZodString;
    is_default: z.ZodBoolean;
    git_branch: z.ZodOptional<z.ZodString>;
    pr_number: z.ZodOptional<z.ZodNumber>;
    latest_check_run_id: z.ZodOptional<z.ZodNumber>;
    persistent: z.ZodBoolean;
    status: z.ZodEnum<{
        CREATING_PROJECT: "CREATING_PROJECT";
        RUNNING_MIGRATIONS: "RUNNING_MIGRATIONS";
        MIGRATIONS_PASSED: "MIGRATIONS_PASSED";
        MIGRATIONS_FAILED: "MIGRATIONS_FAILED";
        FUNCTIONS_DEPLOYED: "FUNCTIONS_DEPLOYED";
        FUNCTIONS_FAILED: "FUNCTIONS_FAILED";
    }>;
    created_at: z.ZodString;
    updated_at: z.ZodString;
}, z.core.$strip>;
declare const edgeFunctionSchema: z.ZodObject<{
    id: z.ZodString;
    slug: z.ZodString;
    name: z.ZodString;
    status: z.ZodString;
    version: z.ZodNumber;
    created_at: z.ZodOptional<z.ZodNumber>;
    updated_at: z.ZodOptional<z.ZodNumber>;
    verify_jwt: z.ZodOptional<z.ZodBoolean>;
    import_map: z.ZodOptional<z.ZodBoolean>;
    import_map_path: z.ZodOptional<z.ZodString>;
    entrypoint_path: z.ZodOptional<z.ZodString>;
}, z.core.$strip>;
declare const edgeFunctionWithBodySchema: z.ZodObject<{
    id: z.ZodString;
    slug: z.ZodString;
    name: z.ZodString;
    status: z.ZodString;
    version: z.ZodNumber;
    created_at: z.ZodOptional<z.ZodNumber>;
    updated_at: z.ZodOptional<z.ZodNumber>;
    verify_jwt: z.ZodOptional<z.ZodBoolean>;
    import_map: z.ZodOptional<z.ZodBoolean>;
    import_map_path: z.ZodOptional<z.ZodString>;
    entrypoint_path: z.ZodOptional<z.ZodString>;
    files: z.ZodArray<z.ZodObject<{
        name: z.ZodString;
        content: z.ZodString;
    }, z.core.$strip>>;
}, z.core.$strip>;
declare const createProjectOptionsSchema: z.ZodObject<{
    name: z.ZodString;
    organization_id: z.ZodString;
    region: z.ZodEnum<{
        "us-west-1": "us-west-1";
        "us-east-1": "us-east-1";
        "us-east-2": "us-east-2";
        "ca-central-1": "ca-central-1";
        "eu-west-1": "eu-west-1";
        "eu-west-2": "eu-west-2";
        "eu-west-3": "eu-west-3";
        "eu-central-1": "eu-central-1";
        "eu-central-2": "eu-central-2";
        "eu-north-1": "eu-north-1";
        "ap-south-1": "ap-south-1";
        "ap-southeast-1": "ap-southeast-1";
        "ap-northeast-1": "ap-northeast-1";
        "ap-northeast-2": "ap-northeast-2";
        "ap-southeast-2": "ap-southeast-2";
        "sa-east-1": "sa-east-1";
    }>;
    db_pass: z.ZodOptional<z.ZodString>;
}, z.core.$strip>;
declare const createBranchOptionsSchema: z.ZodObject<{
    name: z.ZodString;
}, z.core.$strip>;
declare const resetBranchOptionsSchema: z.ZodObject<{
    migration_version: z.ZodOptional<z.ZodString>;
}, z.core.$strip>;
declare const deployEdgeFunctionOptionsSchema: z.ZodObject<{
    name: z.ZodString;
    entrypoint_path: z.ZodString;
    import_map_path: z.ZodOptional<z.ZodString>;
    verify_jwt: z.ZodOptional<z.ZodBoolean>;
    files: z.ZodArray<z.ZodObject<{
        name: z.ZodString;
        content: z.ZodString;
    }, z.core.$strip>>;
}, z.core.$strip>;
declare const executeSqlOptionsSchema: z.ZodObject<{
    query: z.ZodString;
    parameters: z.ZodOptional<z.ZodArray<z.ZodUnknown>>;
    read_only: z.ZodOptional<z.ZodBoolean>;
}, z.core.$strip>;
declare const applyMigrationOptionsSchema: z.ZodObject<{
    name: z.ZodString;
    query: z.ZodString;
}, z.core.$strip>;
declare const migrationSchema: z.ZodObject<{
    version: z.ZodString;
    name: z.ZodOptional<z.ZodString>;
}, z.core.$strip>;
declare const logsServiceSchema: z.ZodEnum<{
    api: "api";
    "branch-action": "branch-action";
    postgres: "postgres";
    "edge-function": "edge-function";
    auth: "auth";
    storage: "storage";
    realtime: "realtime";
}>;
declare const getLogsOptionsSchema: z.ZodObject<{
    service: z.ZodEnum<{
        api: "api";
        "branch-action": "branch-action";
        postgres: "postgres";
        "edge-function": "edge-function";
        auth: "auth";
        storage: "storage";
        realtime: "realtime";
    }>;
    iso_timestamp_start: z.ZodOptional<z.ZodString>;
    iso_timestamp_end: z.ZodOptional<z.ZodString>;
}, z.core.$strip>;
declare const generateTypescriptTypesResultSchema: z.ZodObject<{
    types: z.ZodString;
}, z.core.$strip>;
type Organization = z.infer<typeof organizationSchema>;
type Project = z.infer<typeof projectSchema>;
type Branch = z.infer<typeof branchSchema>;
type EdgeFunction = z.infer<typeof edgeFunctionSchema>;
type EdgeFunctionWithBody = z.infer<typeof edgeFunctionWithBodySchema>;
type CreateProjectOptions = z.infer<typeof createProjectOptionsSchema>;
type CreateBranchOptions = z.infer<typeof createBranchOptionsSchema>;
type ResetBranchOptions = z.infer<typeof resetBranchOptionsSchema>;
type DeployEdgeFunctionOptions = z.infer<typeof deployEdgeFunctionOptionsSchema>;
type ExecuteSqlOptions = z.infer<typeof executeSqlOptionsSchema>;
type ApplyMigrationOptions = z.infer<typeof applyMigrationOptionsSchema>;
type Migration = z.infer<typeof migrationSchema>;
type ListMigrationsResult = z.infer<typeof migrationSchema>;
type LogsService = z.infer<typeof logsServiceSchema>;
type GetLogsOptions = z.infer<typeof getLogsOptionsSchema>;
type GenerateTypescriptTypesResult = z.infer<typeof generateTypescriptTypesResultSchema>;
type StorageConfig = z.infer<typeof storageConfigSchema>;
type StorageBucket = z.infer<typeof storageBucketSchema>;
type DatabaseOperations = {
    executeSql<T>(projectId: string, options: ExecuteSqlOptions): Promise<T[]>;
    listMigrations(projectId: string): Promise<Migration[]>;
    applyMigration(projectId: string, options: ApplyMigrationOptions): Promise<void>;
};
type AccountOperations = {
    listOrganizations(): Promise<Pick<Organization, 'id' | 'name'>[]>;
    getOrganization(organizationId: string): Promise<Organization>;
    listProjects(): Promise<Project[]>;
    getProject(projectId: string): Promise<Project>;
    createProject(options: CreateProjectOptions): Promise<Project>;
    pauseProject(projectId: string): Promise<void>;
    restoreProject(projectId: string): Promise<void>;
};
type EdgeFunctionsOperations = {
    listEdgeFunctions(projectId: string): Promise<EdgeFunction[]>;
    getEdgeFunction(projectId: string, functionSlug: string): Promise<EdgeFunctionWithBody>;
    deployEdgeFunction(projectId: string, options: DeployEdgeFunctionOptions): Promise<Omit<EdgeFunction, 'files'>>;
};
type DebuggingOperations = {
    getLogs(projectId: string, options: GetLogsOptions): Promise<unknown>;
    getSecurityAdvisors(projectId: string): Promise<unknown>;
    getPerformanceAdvisors(projectId: string): Promise<unknown>;
};
declare const apiKeyTypeSchema: z.ZodEnum<{
    legacy: "legacy";
    publishable: "publishable";
}>;
type ApiKeyType = z.infer<typeof apiKeyTypeSchema>;
type ApiKey = {
    api_key: string;
    name: string;
    type: ApiKeyType;
    description?: string;
    id?: string;
    disabled?: boolean;
};
type DevelopmentOperations = {
    getProjectUrl(projectId: string): Promise<string>;
    getPublishableKeys(projectId: string): Promise<ApiKey[]>;
    generateTypescriptTypes(projectId: string): Promise<GenerateTypescriptTypesResult>;
};
type StorageOperations = {
    getStorageConfig(projectId: string): Promise<StorageConfig>;
    updateStorageConfig(projectId: string, config: StorageConfig): Promise<void>;
    listAllBuckets(projectId: string): Promise<StorageBucket[]>;
};
type BranchingOperations = {
    listBranches(projectId: string): Promise<Branch[]>;
    createBranch(projectId: string, options: CreateBranchOptions): Promise<Branch>;
    deleteBranch(branchId: string): Promise<void>;
    mergeBranch(branchId: string): Promise<void>;
    resetBranch(branchId: string, options: ResetBranchOptions): Promise<void>;
    rebaseBranch(branchId: string): Promise<void>;
};
type SupabasePlatform = {
    init?(info: InitData): Promise<void>;
    account?: AccountOperations;
    database?: DatabaseOperations;
    functions?: EdgeFunctionsOperations;
    debugging?: DebuggingOperations;
    development?: DevelopmentOperations;
    storage?: StorageOperations;
    branching?: BranchingOperations;
};

export { type AccountOperations, type ApiKey, type ApiKeyType, type ApplyMigrationOptions, type Branch, type BranchingOperations, type CreateBranchOptions, type CreateProjectOptions, type DatabaseOperations, type DebuggingOperations, type DeployEdgeFunctionOptions, type DevelopmentOperations, type EdgeFunction, type EdgeFunctionWithBody, type EdgeFunctionsOperations, type ExecuteSqlOptions, type GenerateTypescriptTypesResult, type GetLogsOptions, type ListMigrationsResult, type LogsService, type Migration, type Organization, type Project, type ResetBranchOptions, type StorageBucket, type StorageConfig, type StorageOperations, type SuccessResponse, type SupabasePlatform, apiKeyTypeSchema, applyMigrationOptionsSchema, branchSchema, createBranchOptionsSchema, createProjectOptionsSchema, deployEdgeFunctionOptionsSchema, edgeFunctionSchema, edgeFunctionWithBodySchema, executeSqlOptionsSchema, generateTypescriptTypesResultSchema, getLogsOptionsSchema, logsServiceSchema, migrationSchema, organizationSchema, projectSchema, resetBranchOptionsSchema, storageBucketSchema, storageConfigSchema };
