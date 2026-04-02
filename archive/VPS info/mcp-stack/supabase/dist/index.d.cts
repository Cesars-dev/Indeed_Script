import { ToolCallCallback } from '@supabase/mcp-utils';
export { ToolCallCallback } from '@supabase/mcp-utils';
import { SupabasePlatform } from './platform/index.cjs';
import * as _modelcontextprotocol_sdk_server from '@modelcontextprotocol/sdk/server';
import { z } from 'zod/v4';

declare const CURRENT_FEATURE_GROUPS: readonly ["docs", "account", "database", "debugging", "development", "functions", "branching", "storage"];
declare const featureGroupSchema: z.ZodPipe<z.ZodUnion<readonly [z.ZodEnum<{
    debug: "debug";
}>, z.ZodEnum<{
    storage: "storage";
    docs: "docs";
    account: "account";
    database: "database";
    debugging: "debugging";
    development: "development";
    functions: "functions";
    branching: "branching";
}>]>, z.ZodTransform<"storage" | "docs" | "account" | "database" | "debugging" | "development" | "functions" | "branching", "storage" | "docs" | "account" | "database" | "debugging" | "development" | "functions" | "branching" | "debug">>;
type FeatureGroup = z.infer<typeof featureGroupSchema>;

type SupabaseMcpServerOptions = {
    /**
     * Platform implementation for Supabase.
     */
    platform: SupabasePlatform;
    /**
     * The API URL for the Supabase Content API.
     */
    contentApiUrl?: string;
    /**
     * The project ID to scope the server to.
     *
     * If undefined, the server will have access
     * to all organizations and projects for the user.
     */
    projectId?: string;
    /**
     * Executes database queries in read-only mode if true.
     */
    readOnly?: boolean;
    /**
     * Features to enable.
     * Options: 'account', 'branching', 'database', 'debugging', 'development', 'docs', 'functions', 'storage'
     */
    features?: string[];
    /**
     * Callback for after a supabase tool is called.
     */
    onToolCall?: ToolCallCallback;
};
/**
 * Creates an MCP server for interacting with Supabase.
 */
declare function createSupabaseMcpServer(options: SupabaseMcpServerOptions): _modelcontextprotocol_sdk_server.Server<{
    method: string;
    params?: {
        [x: string]: unknown;
        _meta?: {
            [x: string]: unknown;
            progressToken?: string | number | undefined;
            "io.modelcontextprotocol/related-task"?: {
                taskId: string;
            } | undefined;
        } | undefined;
    } | undefined;
}, {
    method: string;
    params?: {
        [x: string]: unknown;
        _meta?: {
            [x: string]: unknown;
            progressToken?: string | number | undefined;
            "io.modelcontextprotocol/related-task"?: {
                taskId: string;
            } | undefined;
        } | undefined;
    } | undefined;
}, {
    [x: string]: unknown;
    _meta?: {
        [x: string]: unknown;
        progressToken?: string | number | undefined;
        "io.modelcontextprotocol/related-task"?: {
            taskId: string;
        } | undefined;
    } | undefined;
}>;

declare const version: string;

export { CURRENT_FEATURE_GROUPS, type FeatureGroup, type SupabaseMcpServerOptions, SupabasePlatform, createSupabaseMcpServer, version };
