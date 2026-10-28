// Zotero: Tools > Developer > Run JavaScript, with "Run as async function" enabled.
// Select the translated PDF attachments, or their parent paper, before running.
// Unmarked .dual.pdf files from this skill use the engine's default LR layout.
const defaultDualLayout = "LR"; // Change to "TB" for alternating-page output.

function formatTitle(filename) {
    if (/\.mono\.pdf$/i.test(filename)) return "纯中文（mono）";
    if (/\.LR_dual\.pdf$/i.test(filename)) return "双栏中英对照（dual）";
    if (/\.TB_dual\.pdf$/i.test(filename)) return "逐页中英对照（dual）";
    if (/\.dual\.pdf$/i.test(filename)) {
        return defaultDualLayout === "LR"
            ? "双栏中英对照（dual）"
            : "逐页中英对照（dual）";
    }
    return null;
}

const selected = Zotero.getActiveZoteroPane().getSelectedItems();
const attachments = new Map();
for (const item of selected) {
    const children = item.isAttachment()
        ? [item]
        : Zotero.Items.get(item.getAttachments());
    for (const child of children) attachments.set(child.id, child);
}

const changed = [];
for (const attachment of attachments.values()) {
    const path = await attachment.getFilePathAsync();
    if (!path) continue;
    const label = formatTitle(PathUtils.filename(path));
    if (!label) continue;
    const parent = attachment.parentItemID
        ? Zotero.Items.get(attachment.parentItemID)
        : null;
    const shortTitle = parent ? parent.getField("shortTitle") : "";
    const title = shortTitle ? `${shortTitle}-${label}` : label;
    const oldTitle = attachment.getField("title");
    if (oldTitle === title) continue;
    attachment.setField("title", title);
    await attachment.saveTx();
    changed.push({ key: attachment.key, oldTitle, title });
}
return changed.length ? changed : "没有需要更新的译文附件；请选择译文 PDF 或其父条目。";
