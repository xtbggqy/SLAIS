// renderer.js
document.addEventListener('DOMContentLoaded', function() {
    // 获取API接口选择元素
    const apiSelect = document.querySelector('select[name="API接口"]');
    // 获取文本大模型选择元素
    const textModelSelect = document.querySelector('select[name="文本大模型"]');
    
    // API接口与模型列表的映射
    const apiToModels = {
        "OpenAI": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"],
        "Gemini": ["gemini-pro", "gemini-1.0-pro", "gemini-1.5-pro"],
        "xAI": ["grok-1", "grok-2"],
        "阿里云": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "DeepSeek": ["deepseek-chat", "deepseek-math"],
        "OpenRouter": ["openrouter-auto", "openrouter-model-1", "openrouter-model-2"]
    };
    
    // 当API接口选择变化时，更新文本大模型选项
    if (apiSelect && textModelSelect) {
        apiSelect.addEventListener('change', function() {
            const selectedApi = apiSelect.value;
            const models = apiToModels[selectedApi] || [];
            
            // 清空当前文本大模型选项
            textModelSelect.innerHTML = '';
            
            // 添加新的模型选项
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                textModelSelect.appendChild(option);
            });
        });
    }
    
    // 初始化页面时根据默认API接口设置模型列表
    if (apiSelect && textModelSelect) {
        const defaultApi = apiSelect.value;
        const defaultModels = apiToModels[defaultApi] || [];
        
        defaultModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            textModelSelect.appendChild(option);
        });
    }
});
