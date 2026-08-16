import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Extension for Prompt Stack
app.registerExtension({
    name: "PromptStack",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {

        if (nodeData.name === "PromptStack") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;

            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // Flag to track if we're in a restore scenario
                this._isRestoring = false;

                // Initialize entries storage
                this._promptEntries = [];

                // Function to load categories
                const loadCategories = async () => {
                    try {
                        const response = await api.fetchApi("/prompt_db_categories", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({})
                        });

                        if (response.ok) {
                            const data = await response.json();
                            return data.categories || [];
                        }
                    } catch (error) {
                        console.error("Error loading categories:", error);
                    }
                    return [];
                };

                // Function to load prompts for a category
                const loadPrompts = async (category) => {
                    try {
                        const response = await api.fetchApi("/prompt_db_prompts", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                category: category
                            })
                        });

                        if (response.ok) {
                            const data = await response.json();
                            return data.prompts || [];
                        }
                    } catch (error) {
                        console.error("Error loading prompts:", error);
                    }
                    return [];
                };

                // Function to load prompt text
                const loadPromptText = async (category, promptName) => {
                    try {
                        const response = await api.fetchApi("/prompt_db_text", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                category: category,
                                prompt_name: promptName
                            })
                        });

                        if (response.ok) {
                            const data = await response.json();
                            return data.prompt_text || "";
                        }
                    } catch (error) {
                        console.error("Error loading prompt text:", error);
                    }
                    return "";
                };

                // --- ENTRY BOOKKEEPING ---
                // An entry is the triple prompt_N_category / _name / _enabled.
                const entryWidgets = () => this.widgets.filter(
                    w => w.name && /^prompt_\d+_enabled$/.test(w.name)
                );

                const entryNumberOf = (enabledWidget) => parseInt(enabledWidget.name.split('_')[1], 10);

                const nextEntryNumber = () => {
                    // Highest in use + 1, never a count: removing a middle entry
                    // would otherwise hand the next one a number already taken,
                    // and ComfyUI maps widgets to inputs by name - two widgets
                    // called prompt_3_category collapse into one and an entry
                    // vanishes from the generated prompt.
                    const numbers = entryWidgets().map(entryNumberOf).filter(n => !isNaN(n));
                    return numbers.length ? Math.max(...numbers) + 1 : 1;
                };

                // Compact the numbering back to 1..N after a removal, so the
                // numbers on screen match the entries and never drift apart.
                const renumberEntries = () => {
                    entryWidgets().forEach((enabledWidget, index) => {
                        const oldNum = entryNumberOf(enabledWidget);
                        const newNum = index + 1;
                        if (oldNum === newNum) return;

                        const categoryWidget = this.widgets.find(w => w.name === `prompt_${oldNum}_category`);
                        const promptWidget = this.widgets.find(w => w.name === `prompt_${oldNum}_name`);
                        if (categoryWidget) categoryWidget.name = `prompt_${newNum}_category`;
                        if (promptWidget) promptWidget.name = `prompt_${newNum}_name`;
                        enabledWidget.name = `prompt_${newNum}_enabled`;

                        const removeButton = this.widgets.find(w => w._promptStackEntry === enabledWidget);
                        if (removeButton) removeButton.name = `❌ Remove Entry ${newNum}`;
                    });
                };

                // Function to build and update preview
                const updatePreview = async () => {
                    const previewWidget = this.widgets.find(w => w.name === 'preview_text');
                    const separatorWidget = this.widgets.find(w => w.name === 'separator');

                    if (!previewWidget || !separatorWidget) return;

                    const separator = separatorWidget.value || ", ";
                    const stacked_prompts = [];

                    for (const enabledWidget of entryWidgets()) {
                        const entryNum = entryNumberOf(enabledWidget);
                        const categoryWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_category`);
                        const promptWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_name`);

                        if (enabledWidget.value && categoryWidget && promptWidget && categoryWidget.value && promptWidget.value) {
                            try {
                                const promptText = await loadPromptText(categoryWidget.value, promptWidget.value);
                                if (promptText) {
                                    stacked_prompts.push(promptText);
                                }
                            } catch (error) {
                                console.error("Error loading prompt text for preview:", error);
                            }
                        }
                    }

                    const result = stacked_prompts.join(separator);
                    previewWidget.value = result;

                    if (previewWidget.inputEl) {
                        previewWidget.inputEl.value = result;
                    }
                };

                const updateCategoryDropdown = async (categoryWidget, restoredCategoryName = null) => {
                    const categories = await loadCategories();
                    categoryWidget.options.values = categories;

                    if (restoredCategoryName && categories.includes(restoredCategoryName)) {
                        categoryWidget.value = restoredCategoryName;
                    } else {
                        categoryWidget.value = categories.length > 0 ? categories[0] : "";
                    }

                    if (categoryWidget.inputEl) {
                        categoryWidget.inputEl.innerHTML = "";
                        categories.forEach(category => {
                            const option = document.createElement("option");
                            option.value = category;
                            option.textContent = category;
                            if (category === categoryWidget.value) {
                                option.selected = true;
                            }
                            categoryWidget.inputEl.appendChild(option);
                        });
                    }
                };

                const updatePromptDropdown = async (categoryWidget, promptWidget, restoredPromptName = null) => {
                    if (categoryWidget.value) {
                        const prompts = await loadPrompts(categoryWidget.value);
                        promptWidget.options.values = prompts;

                        if (restoredPromptName && prompts.includes(restoredPromptName)) {
                            promptWidget.value = restoredPromptName;
                        } else {
                            promptWidget.value = prompts.length > 0 ? prompts[0] : "";
                        }

                        if (promptWidget.inputEl) {
                            promptWidget.inputEl.innerHTML = "";
                            prompts.forEach(prompt => {
                                const option = document.createElement("option");
                                option.value = prompt;
                                option.textContent = prompt;
                                if (prompt === promptWidget.value) {
                                    option.selected = true;
                                }
                                promptWidget.inputEl.appendChild(option);
                            });
                        }
                    }
                };

                // Sync current widget values to _promptEntries
                const syncEntries = () => {
                    const entries = [];
                    for (const enabledWidget of entryWidgets()) {
                        const entryNum = entryNumberOf(enabledWidget);
                        const categoryWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_category`);
                        const promptWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_name`);
                        if (categoryWidget && promptWidget) {
                            entries.push({
                                category: categoryWidget.value,
                                name: promptWidget.value,
                                enabled: enabledWidget.value
                            });
                        }
                    }
                    this._promptEntries = entries;

                    // properties is part of the node schema, so the entries
                    // survive round-trips that strip unknown top-level keys.
                    this.properties = this.properties || {};
                    this.properties.promptStack_entries = entries;
                };

                const setupCategoryHandler = (entryNum) => {
                    const categoryWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_category`);
                    const promptWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_name`);
                    const enabledWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_enabled`);

                    if (categoryWidget && promptWidget) {
                        const originalCategoryCallback = categoryWidget.callback;
                        categoryWidget.callback = function(value) {
                            if (originalCategoryCallback) {
                                originalCategoryCallback.call(this, value);
                            }
                            (async () => {
                                await updatePromptDropdown(categoryWidget, promptWidget);
                                syncEntries();
                                await updatePreview();
                            })();
                        };

                        const originalPromptCallback = promptWidget.callback;
                        promptWidget.callback = function(value) {
                            if (originalPromptCallback) {
                                originalPromptCallback.call(this, value);
                            }
                            syncEntries();
                            setTimeout(() => updatePreview(), 100);
                        };

                        if (enabledWidget) {
                            const originalEnabledCallback = enabledWidget.callback;
                            enabledWidget.callback = function(value) {
                                if (originalEnabledCallback) {
                                    originalEnabledCallback.call(this, value);
                                }
                                syncEntries();
                                setTimeout(() => updatePreview(), 100);
                            };
                        }

                        if (categoryWidget.value) {
                            updatePromptDropdown(categoryWidget, promptWidget);
                        }
                    }
                };

                // The button holds direct references to the widgets it owns.
                // Deleting by name meant a repeated entry number wiped out two
                // entries at once.
                const addRemoveButton = (categoryWidget, promptWidget, enabledWidget, entryNum) => {
                    const button = this.addWidget("button", `❌ Remove Entry ${entryNum}`, "", () => {
                        for (const widget of [categoryWidget, promptWidget, enabledWidget, button]) {
                            const index = this.widgets.indexOf(widget);
                            if (index !== -1) {
                                this.widgets.splice(index, 1);
                            }
                        }
                        renumberEntries();
                        syncEntries();
                        this.computeSize();
                        this.setDirtyCanvas(true, true);
                        setTimeout(() => updatePreview(), 100);
                    }, { serialize: false });
                    button._promptStackEntry = enabledWidget;
                    return button;
                };

                // Wire up entries that already exist as widgets: prompt_1_* is
                // declared by INPUT_TYPES, and LiteGraph restores its values
                // positionally from widgets_values.
                const attachExistingEntries = () => {
                    for (const enabledWidget of entryWidgets()) {
                        if (this.widgets.some(w => w._promptStackEntry === enabledWidget)) continue;

                        const entryNum = entryNumberOf(enabledWidget);
                        const categoryWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_category`);
                        const promptWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_name`);
                        if (!categoryWidget || !promptWidget) continue;

                        setupCategoryHandler(entryNum);
                        addRemoveButton(categoryWidget, promptWidget, enabledWidget, entryNum);
                    }
                };

                const refreshAllDropdowns = async () => {
                    console.log('[PromptStack] Refreshing all dropdowns with fresh data');

                    const categoryWidgets = this.widgets.filter(w => w.name && w.name.startsWith("prompt_") && w.name.endsWith("_category"));

                    for (const categoryWidget of categoryWidgets) {
                        const entryNum = categoryWidget.name.split('_')[1];
                        const promptWidget = this.widgets.find(w => w.name === `prompt_${entryNum}_name`);

                        if (promptWidget) {
                            const currentCategory = categoryWidget.value;
                            const currentPrompt = promptWidget.value;

                            await updateCategoryDropdown(categoryWidget, currentCategory);
                            await updatePromptDropdown(categoryWidget, promptWidget, currentPrompt);
                        }
                    }

                    setTimeout(() => updatePreview(), 100);
                };

                const addPromptEntry = async (init = {}, entryNum = -1) => {
                    if (entryNum === -1) {
                        entryNum = nextEntryNumber();
                    }

                    const categories = await loadCategories();
                    let selectedCategory = init.category || (categories.length > 0 ? categories[0] : "");

                    let prompts = [];
                    if (selectedCategory) {
                        prompts = await loadPrompts(selectedCategory);
                    }

                    let selectedPrompt = init.name || (prompts.length > 0 ? prompts[0] : "");

                    const categoryWidget = this.addWidget("combo", `prompt_${entryNum}_category`, selectedCategory, null, { values: [...categories] });
                    const promptWidget = this.addWidget("combo", `prompt_${entryNum}_name`, selectedPrompt, null, { values: [...prompts] });
                    const enabledWidget = this.addWidget("toggle", `prompt_${entryNum}_enabled`, init.enabled !== undefined ? init.enabled : true, null);

                    setupCategoryHandler(entryNum);
                    addRemoveButton(categoryWidget, promptWidget, enabledWidget, entryNum);

                    if (init.name) {
                        promptWidget.value = init.name;
                    }

                    await updatePromptDropdown(categoryWidget, promptWidget, init.name);
                    syncEntries();

                    this.computeSize();
                    this.setDirtyCanvas(true, true);
                };

                const createPreviewWidgets = () => {
                    const previewWidget = this.widgets.find(w => w.name === 'preview_text');
                    if (previewWidget) {
                        if (previewWidget.inputEl) {
                            previewWidget.inputEl.readOnly = true;
                            previewWidget.inputEl.placeholder = "Preview of stacked prompts will appear here...";
                        }

                        const separatorWidget = this.widgets.find(w => w.name === 'separator');
                        if (separatorWidget && !separatorWidget._promptStackHooked) {
                            const originalSeparatorCallback = separatorWidget.callback;
                            separatorWidget.callback = function(value) {
                                if (originalSeparatorCallback) {
                                    originalSeparatorCallback.call(this, value);
                                }
                                setTimeout(() => updatePreview(), 100);
                            };
                            separatorWidget._promptStackHooked = true;
                        }

                        this.computeSize();
                        this.setDirtyCanvas(true, true);
                    }
                };

                // Control buttons sit directly under the preview. They are
                // tagged rather than matched by their caption, because
                // addWidget stores that caption as `name`, never as `label`.
                const removeControlButtons = () => {
                    this.widgets
                        .filter(w => w._promptStackControl)
                        .forEach(widget => this.widgets.splice(this.widgets.indexOf(widget), 1));
                };

                const installControlButtons = () => {
                    const previewIndex = this.widgets.findIndex(w => w.name === 'preview_text');
                    if (previewIndex === -1) return;

                    const placeAfter = (button, afterIndex) => {
                        button._promptStackControl = true;
                        const index = this.widgets.indexOf(button);
                        if (index > afterIndex + 1) {
                            this.widgets.splice(index, 1);
                            this.widgets.splice(afterIndex + 1, 0, button);
                        }
                    };

                    const reloadButton = this.addWidget("button", "🔄 Reload DB", "", () => {
                        refreshAllDropdowns();
                    }, { serialize: false });
                    placeAfter(reloadButton, previewIndex);

                    const addButton = this.addWidget("button", "➕ Add Prompt Entry", "", () => {
                        addPromptEntry();
                    }, { serialize: false });
                    placeAfter(addButton, this.widgets.indexOf(reloadButton));
                };

                // Add buttons and initialize first entry (only for new nodes, not restored)
                setTimeout(() => {
                    if (this._isRestoring) return;

                    createPreviewWidgets();
                    installControlButtons();
                    attachExistingEntries();
                    refreshAllDropdowns();
                    syncEntries();
                }, 50);

                // --- SERIALIZATION ---
                this.serialize_widgets = true;

                // LiteGraph discards whatever onSerialize returns; the data has
                // to be written into the object it hands in.
                this.onSerialize = function(o) {
                    if (!o) return;

                    // Read the entries off the widgets rather than trusting the
                    // cache: not every path that changes a value is one of ours.
                    syncEntries();

                    // Buttons carry no value worth keeping, and leaving them in
                    // widgets_values shifts every later value by one when
                    // LiteGraph assigns them back positionally on load.
                    // separator and preview_text stay, so the first values line
                    // up with the widgets a fresh node is created with.
                    const values = [];
                    for (const widget of this.widgets) {
                        if (widget.type === 'button') continue;
                        if (typeof widget.serializeValue === 'function') {
                            values.push(widget.serializeValue(this, values.length));
                        } else if (widget.value !== undefined) {
                            values.push(widget.value);
                        }
                    }
                    o.widgets_values = values;

                    const entries = this._promptEntries || [];
                    o.properties = Object.assign({}, o.properties, { promptStack_entries: entries });
                    // Also kept where older versions of this node wrote it
                    o.promptStack_entries = entries;
                };

                // Restore the entries, chaining to ComfyUI's own handler
                const originalOnConfigure = this.onConfigure;
                this.onConfigure = async function(info) {
                    console.log('[PromptStack] onConfigure called', info);

                    // Core restores widget values and any widget that was
                    // converted to an input - it must still run.
                    if (originalOnConfigure) {
                        originalOnConfigure.apply(this, arguments);
                    }

                    this._isRestoring = true;

                    const savedEntries = info?.properties?.promptStack_entries
                        || info?.promptStack_entries
                        || [];

                    // Rebuild the controls in one synchronous pass, so their
                    // position does not depend on how fast the server answers.
                    removeControlButtons();
                    createPreviewWidgets();
                    installControlButtons();

                    if (Array.isArray(savedEntries) && savedEntries.length > 0) {
                        console.log('[PromptStack] Restoring entries:', savedEntries);

                        const staleWidgets = this.widgets.filter(
                            w => (w.name && w.name.startsWith('prompt_')) || w._promptStackEntry
                        );
                        staleWidgets.forEach(widget => {
                            this.widgets.splice(this.widgets.indexOf(widget), 1);
                        });

                        for (let i = 0; i < savedEntries.length; i++) {
                            await addPromptEntry(savedEntries[i], i + 1);
                        }
                    } else {
                        // No entry list in the workflow - keep whatever
                        // LiteGraph restored into the declared prompt_1_*
                        // widgets rather than dropping every entry.
                        console.log('[PromptStack] No saved entries, keeping the restored widgets');
                        attachExistingEntries();
                    }

                    syncEntries();
                    console.log('[PromptStack] Widgets after restore:', this.widgets.map(w => w.name || w.type));

                    await refreshAllDropdowns();
                };

                this.onGetInputs = function() {
                    const inputs = {};
                    let promptNum = 1;
                    for (const widget of this.widgets) {
                        if (widget.name === `prompt_${promptNum}_category`) {
                            inputs[`prompt_${promptNum}_category`] = widget.value;
                        } else if (widget.name === `prompt_${promptNum}_name`) {
                            inputs[`prompt_${promptNum}_name`] = widget.value;
                        } else if (widget.name === `prompt_${promptNum}_enabled`) {
                            inputs[`prompt_${promptNum}_enabled`] = widget.value;
                            promptNum++;
                        }
                    }
                    const sepWidget = this.widgets.find(w => w.name === 'separator');
                    if (sepWidget) {
                        inputs['separator'] = sepWidget.value;
                    }
                    return inputs;
                };

                this.computeSize();
                this.setDirtyCanvas(true, true);

                return r;
            };
        }
    }
});
