import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Extension for LoRa Loader with Trigger DB
app.registerExtension({
    name: "LoRaLoaderWithTriggerDB",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "LoRaLoaderWithTriggerDB") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Find the widgets
                const loraWidget = this.widgets.find(w => w.name === "lora_name");
                const allTriggersWidget = this.widgets.find(w => w.name === "all_triggers");
                const activeTriggersWidget = this.widgets.find(w => w.name === "active_triggers");
                
                if (loraWidget && allTriggersWidget && activeTriggersWidget) {
                    // Alternative approach: Use change event instead of overriding callback
                    // This preserves the original filtering behavior completely
                    if (loraWidget.inputEl) {
                        loraWidget.inputEl.addEventListener('change', async (event) => {
                            const value = event.target.value;
                            
                            // Auto-load triggers whenever LoRa changes
                            if (value) {
                                try {
                                    const response = await api.fetchApi("/lora_triggers", {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/json",
                                        },
                                        body: JSON.stringify({
                                            lora_name: value
                                        })
                                    });
                                    
                                    if (response.ok) {
                                        const data = await response.json();
                                        if (data.all_triggers || data.active_triggers) {
                                            allTriggersWidget.value = data.all_triggers || "";
                                            allTriggersWidget.callback && allTriggersWidget.callback(data.all_triggers || "");
                                            
                                            activeTriggersWidget.value = data.active_triggers || "";
                                            activeTriggersWidget.callback && activeTriggersWidget.callback(data.active_triggers || "");
                                        } else {
                                            // Clear fields if no saved triggers
                                            allTriggersWidget.value = "";
                                            allTriggersWidget.callback && allTriggersWidget.callback("");
                                            
                                            activeTriggersWidget.value = "";
                                            activeTriggersWidget.callback && activeTriggersWidget.callback("");
                                        }
                                    }
                                } catch (error) {
                                    // Could not auto-load triggers
                                }
                            }
                        });
                    }
                    
                    // Keep the original callback approach as backup
                    // Store original callback
                    const originalLoraCallback = loraWidget.callback;
                    
                    // Override the LoRa callback to auto-load triggers when LoRa changes
                    // But preserve the original filtering functionality
                    loraWidget.callback = async function(value) {
                        // Call the original callback first to preserve filtering behavior
                        if (originalLoraCallback) {
                            const result = originalLoraCallback.call(this, value);
                            // If the original callback returns something, respect it
                            if (result !== undefined) {
                                return result;
                            }
                        }
                        
                        // Auto-load triggers whenever LoRa changes (backup method)
                        if (value) {
                            // Add a small delay to ensure this is a final selection, not just typing
                            setTimeout(async () => {
                                try {
                                    const response = await api.fetchApi("/lora_triggers", {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/json",
                                        },
                                        body: JSON.stringify({
                                            lora_name: value
                                        })
                                    });
                                    
                                    if (response.ok) {
                                        const data = await response.json();
                                        if (data.all_triggers || data.active_triggers) {
                                            allTriggersWidget.value = data.all_triggers || "";
                                            allTriggersWidget.callback && allTriggersWidget.callback(data.all_triggers || "");
                                            
                                            activeTriggersWidget.value = data.active_triggers || "";
                                            activeTriggersWidget.callback && activeTriggersWidget.callback(data.active_triggers || "");
                                        } else {
                                            // Clear fields if no saved triggers
                                            allTriggersWidget.value = "";
                                            allTriggersWidget.callback && allTriggersWidget.callback("");
                                            
                                            activeTriggersWidget.value = "";
                                            activeTriggersWidget.callback && activeTriggersWidget.callback("");
                                        }
                                    }
                                } catch (error) {
                                    // Could not auto-load triggers
                                }
                            }, 500); // 500ms delay to avoid triggering during typing
                        }
                    };
                    
                    // Add load triggers button
                    this.addWidget("button", "📥 Load Triggers", "", async () => {
                        const loraName = loraWidget.value;
                        if (!loraName) {
                            return;
                        }
                        
                        try {
                            const response = await api.fetchApi("/lora_triggers", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify({
                                    lora_name: loraName
                                })
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                if (data.all_triggers || data.active_triggers) {
                                    if (data.all_triggers) {
                                        allTriggersWidget.value = data.all_triggers;
                                        allTriggersWidget.callback && allTriggersWidget.callback(data.all_triggers);
                                    }
                                    if (data.active_triggers) {
                                        activeTriggersWidget.value = data.active_triggers;
                                        activeTriggersWidget.callback && activeTriggersWidget.callback(data.active_triggers);
                                    }
                                } else {
                                    // No saved triggers found
                                }
                            }
                        } catch (error) {
                            // Error loading triggers
                        }
                    }, { serialize: false });
                    
                    // Add load metadata button
                    this.addWidget("button", "🔍 Load Metadata", "", async () => {
                        const loraName = loraWidget.value;
                        if (!loraName) {
                            return;
                        }
                        
                        try {
                            const response = await api.fetchApi("/lora_metadata", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify({
                                    lora_name: loraName
                                })
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                if (data.success) {
                                    // Load the trigger words from metadata
                                    if (data.all_triggers) {
                                        allTriggersWidget.value = data.all_triggers;
                                        allTriggersWidget.callback && allTriggersWidget.callback(data.all_triggers);
                                    }
                                    if (data.active_triggers) {
                                        activeTriggersWidget.value = data.active_triggers;
                                        activeTriggersWidget.callback && activeTriggersWidget.callback(data.active_triggers);
                                    }
                                    console.log(`Loaded metadata: ${data.message}`);
                                } else {
                                    console.log(`Could not load metadata: ${data.message}`);
                                }
                            }
                        } catch (error) {
                            console.error("Error loading metadata:", error);
                        }
                    }, { serialize: false });
                    
                    // Add save triggers button
                    this.addWidget("button", "💾 Save Triggers", "", async () => {
                        const loraName = loraWidget.value;
                        const allTriggers = allTriggersWidget.value;
                        const activeTriggers = activeTriggersWidget.value;
                        
                        if (!loraName) {
                            return;
                        }
                        
                        if ((!allTriggers || allTriggers.trim() === "") && 
                            (!activeTriggers || activeTriggers.trim() === "")) {
                            return;
                        }
                        
                        try {
                            const response = await api.fetchApi("/lora_triggers_save", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify({
                                    lora_name: loraName,
                                    all_triggers: allTriggers,
                                    active_triggers: activeTriggers
                                })
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                // Successfully saved or failed
                            }
                        } catch (error) {
                            // Error saving triggers
                        }
                    }, { serialize: false });
                    
                    // Force the node to resize to show the new buttons
                    this.computeSize();
                    this.setDirtyCanvas(true, true);
                } else {
                    // Could not find required widgets
                }
                
                return r;
            };
        }
    }
});
