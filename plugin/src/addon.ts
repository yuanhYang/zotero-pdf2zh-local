// base class
import { config } from "../package.json";
import {
    ColumnOptions,
    VirtualizedTableHelper,
    DialogHelper,
} from "zotero-plugin-toolkit";
import hooks from "./hooks";
import { createZToolkit } from "./utils/ztoolkit";
import { LLMApiData } from "./modules/llmApiManager";

class Addon {
    public data: {
        alive: boolean;
        config: typeof config;
        // Env type, see build.js
        env: "development" | "production";
        ztoolkit: ZToolkit;
        locale?: {
            current: any;
        };
        prefs?: {
            window: Window;
            columns: Array<ColumnOptions>;
            rows: Array<{ [dataKey: string]: string }>;
            tableHelper?: VirtualizedTableHelper;
        };
        dialog?: DialogHelper;
        llmApis: {
            map: Map<string, LLMApiData>;
            cachedKeys: string[];
            selectedKey?: string;
        };
    };
    // Lifecycle hooks
    public hooks: typeof hooks;
    // APIs
    public api: object;

    constructor() {
        this.data = {
            alive: true,
            config,
            env: __env__,
            ztoolkit: createZToolkit(),
            llmApis: {
                map: new Map<string, LLMApiData>(),
                cachedKeys: [],
            },
        };
        this.hooks = hooks;
        this.api = {};
    }
}

export default Addon;
