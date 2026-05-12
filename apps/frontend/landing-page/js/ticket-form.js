/**
 * 密钥申请工单系统交互逻辑
 */
(function() {
    // DOM 元素
    const ticketModal = document.getElementById('ticketModal');
    const successModal = document.getElementById('successModal');
    const queryModal = document.getElementById('queryModal');
    const ticketForm = document.getElementById('ticketForm');
    const queryForm = document.getElementById('queryForm');
    
    const getKeyBtns = document.querySelectorAll('.btn-get-key');
    const closeBtns = document.querySelectorAll('.close-modal');
    const cancelBtn = document.getElementById('cancelTicket');
    const openQueryBtn = document.getElementById('openQueryModal');
    
    const ticketTypeSelect = document.getElementById('ticketType');
    const keyTypeGroup = document.getElementById('keyTypeGroup');
    const existingKeyGroup = document.getElementById('existingKeyGroup');
    
    let iti; // intl-tel-input 实例
    const phoneInput = document.getElementById('phone');
    const phoneErrorMsg = document.getElementById('phone-error-msg');
    
    // 初始化
    function init() {
        initIntlTelInput();
        bindEvents();
    }
    
    // 初始化国际电话插件
    function initIntlTelInput() {
        if (!phoneInput) return;
        
        iti = window.intlTelInput(phoneInput, {
            initialCountry: "auto",
            geoIpLookup: function(success, failure) {
                fetch("https://ipapi.co/json")
                    .then(res => res.json())
                    .then(data => success(data.country_code))
                    .catch(() => success("cn"));
            },
            preferredCountries: ["cn", "us", "hk", "gb"],
            utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.19/js/utils.js",
            separateDialCode: true
        });
        
        // 监听输入事件，清除错误状态
        phoneInput.addEventListener('input', () => {
            const group = phoneInput.closest('.ticket-form-group');
            group.classList.remove('has-error');
            if (phoneErrorMsg) phoneErrorMsg.style.display = 'none';
        });
    }
    
    // 绑定事件
    function bindEvents() {
        // 打开申请模态框
        getKeyBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                showModal(ticketModal);
            });
        });
        
        // 关闭模态框
        closeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                hideAllModals();
            });
        });
        
        // 取消按钮
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                hideAllModals();
            });
        }
        
        // 点击遮罩关闭
        [ticketModal, successModal, queryModal].forEach(modal => {
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        hideAllModals();
                    }
                });
            }
        });
        
        // ESC 键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideAllModals();
            }
        });
        
        // 工单类型切换联动
        if (ticketTypeSelect) {
            ticketTypeSelect.addEventListener('change', (e) => {
                const type = e.target.value;
                if (type === 'key_request') {
                    keyTypeGroup.classList.remove('hidden');
                    existingKeyGroup.classList.add('hidden');
                    document.getElementById('existingKey').required = false;
                } else {
                    keyTypeGroup.classList.add('hidden');
                    existingKeyGroup.classList.remove('hidden');
                    document.getElementById('existingKey').required = true;
                }
            });
        }
        
        // 提交工单
        if (ticketForm) {
            ticketForm.addEventListener('submit', handleTicketSubmit);
        }
        
        // 打开查询模态框
        if (openQueryBtn) {
            openQueryBtn.addEventListener('click', (e) => {
                e.preventDefault();
                hideAllModals();
                showModal(queryModal);
            });
        }
        
        // 查询工单
        if (queryForm) {
            queryForm.addEventListener('submit', handleQuerySubmit);
        }
    }
    
    // 显示模态框
    function showModal(modal) {
        if (!modal) return;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden'; // 禁止滚动
        
        // 自动聚焦第一个输入框
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) setTimeout(() => firstInput.focus(), 100);
    }
    
    // 隐藏所有模态框
    function hideAllModals() {
        [ticketModal, successModal, queryModal].forEach(modal => {
            if (modal) modal.classList.remove('active');
        });
        document.body.style.overflow = ''; // 恢复滚动
    }
    
    // 处理工单提交
    async function handleTicketSubmit(e) {
        e.preventDefault();
        
        const submitBtn = ticketForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerText;
        
        // 验证表单
        if (!validateForm(ticketForm)) return;
        
        // 收集数据
        const formData = new FormData(ticketForm);
        const data = Object.fromEntries(formData.entries());
        
        // 获取 E.164 标准格式手机号
        if (iti) {
            data.phone = iti.getNumber();
        }
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
        
        try {
            submitBtn.disabled = true;
            submitBtn.innerText = '提交中...';
            
            // 使用正确的 API 路由 /api/tickets (假设前端代理前缀已处理)
            const response = await fetch('/api/tickets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const result = await response.json();
                // 确保 API 成功后返回真实的数据库 ticket_id
                showSuccess(result.data.ticket_id);
                ticketForm.reset();
            } else {
                const err = await response.json();
                showError(ticketForm, err.message || '提交失败，请稍后重试');
            }
        } catch (error) {
            console.error('Submit error:', error);
            if (error.name === 'AbortError') {
                showError(ticketForm, '提交请求超时，请检查网络后重试');
            } else {
                showError(ticketForm, '网络连接失败，请稍后重试');
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
        }
    }
    
    // 处理查询提交
    async function handleQuerySubmit(e) {
        e.preventDefault();
        
        const queryId = document.getElementById('queryTicketId').value;
        const queryEmail = document.getElementById('queryEmail').value;
        const resultArea = document.getElementById('queryResultArea');
        
        try {
            resultArea.innerHTML = `<p>${t('ticket.queryResult.searching')}</p>`;
            resultArea.classList.remove('hidden');
            
            // 模拟 API 调用
            const response = await fetch(`/api/tickets/${queryId}?email=${encodeURIComponent(queryEmail)}`);
            
            if (response.ok) {
                const result = await response.json();
                // 后端返回格式: { success: true, data: { ticket: {...} } }
                const data = result.data?.ticket || result;
                displayQueryResult(data);
            } else {
                resultArea.innerHTML = `<p class="error-msg" style="display:block">${t('ticket.queryResult.notFound')}</p>`;
            }
        } catch (e) {
            console.error('Query error:', e);
            resultArea.innerHTML = `<p class="error-msg" style="display:block">${t('ticket.queryResult.notFound')}</p>`;
        }
    }

    // 显示错误信息
    function showError(form, message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-msg';
        errorDiv.style.display = 'block';
        errorDiv.style.textAlign = 'center';
        errorDiv.style.marginBottom = '1rem';
        errorDiv.innerText = message;
        
        const existingError = form.querySelector('.form-global-error');
        if (existingError) existingError.remove();
        
        errorDiv.classList.add('form-global-error');
        form.prepend(errorDiv);
        
        setTimeout(() => errorDiv.remove(), 5000);
    }
    
    // 获取 i18n 翻译
    function t(key) {
        if (window.UDAKEI18N) {
            const lang = window.UDAKEI18N.getCurrentLanguage();
            // 从 translations 字典获取
            const dict = (window.UDAKEI18N._translations || {})[lang] || {};
            return key.split('.').reduce((obj, k) => (obj && obj[k] !== undefined ? obj[k] : null), dict) || key;
        }
        return key;
    }

    // 显示查询结果
    function displayQueryResult(data) {
        const resultArea = document.getElementById('queryResultArea');
        
        // 状态样式映射
        const statusClassMap = {
            'pending': 'status-pending',
            'approved': 'status-approved',
            'completed': 'status-completed',
            'rejected': 'status-rejected'
        };
        const statusClass = statusClassMap[data.status] || '';
        const statusText = t('ticket.queryResult.statusMap.' + data.status) || data.status;
        
        // 密钥类型本地化
        const keyTypeText = t('ticket.queryResult.keyTypeMap.' + data.key_type) || data.key_type || '';
        
        // 根据状态决定备注标签：拒绝显示"拒绝原因"，其他显示"备注/处理结果"
        let remarkLabel = '';
        let remarkContent = '';
        if (data.response_message) {
            if (data.status === 'rejected') {
                remarkLabel = t('ticket.queryResult.rejectionReason');
                remarkContent = data.response_message;
            } else {
                remarkLabel = t('ticket.queryResult.remark');
                remarkContent = data.response_message;
            }
        }

        resultArea.innerHTML = `
            <div class="query-result">
                <p><strong>${t('ticket.queryResult.ticketId')}:</strong> ${data.ticket_id}</p>
                <p><strong>${t('ticket.queryResult.status')}:</strong> <span class="status-badge ${statusClass}">${statusText}</span></p>
                <p><strong>${t('ticket.queryResult.created')}:</strong> ${data.created_at}</p>
                ${keyTypeText ? `<p><strong>${t('ticket.queryResult.keyType')}:</strong> ${keyTypeText}</p>` : ''}
                ${data.assigned_key ? `<p><strong>${t('ticket.queryResult.key')}:</strong> <code>${data.assigned_key}</code></p>` : ''}
                ${remarkContent ? `<p><strong>${remarkLabel}:</strong> ${remarkContent}</p>` : ''}
            </div>
        `;
        resultArea.classList.remove('hidden');
    }
    
    // 表单验证
    function validateForm(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
        
        inputs.forEach(input => {
            const group = input.closest('.ticket-form-group');
            if (!input.value.trim()) {
                group.classList.add('has-error');
                isValid = false;
            } else {
                group.classList.remove('has-error');
                
                // 邮箱验证
                if (input.type === 'email' && !validateEmail(input.value)) {
                    group.classList.add('has-error');
                    isValid = false;
                }

                // 用途说明验证
                if (input.id === 'purpose') {
                    if (!validateUsagePurpose(input.value)) {
                        group.classList.add('has-error');
                        const errorMsg = group.querySelector('.error-msg');
                        if (errorMsg) {
                            const lang = window.UDAKEI18N.getCurrentLanguage();
                            errorMsg.innerText = lang === 'zh-CN' ? 
                                '用途说明字数不符合要求（至少15个中文字符或50个英文字符，不含标点）' : 
                                'Purpose length requirement not met (min 15 Chinese or 50 English characters, excluding punctuation)';
                            errorMsg.style.display = 'block';
                        }
                        isValid = false;
                    }
                }

                // 所属单位验证
                if (input.id === 'organization') {
                    const industry = document.getElementById('industry').value;
                    if (!validateOrganization(industry, input.value)) {
                        group.classList.add('has-error');
                        const errorMsg = group.querySelector('.error-msg');
                        if (errorMsg) {
                            const lang = window.UDAKEI18N.getCurrentLanguage();
                            if (industry === '教育') {
                                errorMsg.innerText = lang === 'zh-CN' ? '教育行业所属单位应包含"学院"或"大学"' : 'Organization should contain "College" or "University" for Education industry';
                            } else {
                                errorMsg.innerText = lang === 'zh-CN' ? '所属单位名称不规范（应包含"集团"、"公司"等内容）' : 'Organization name should contain keywords like "Group" or "Company"';
                            }
                            errorMsg.style.display = 'block';
                        }
                        isValid = false;
                    }
                }
                
                // 电话验证
                if (input.id === 'phone') {
                    if (iti && !iti.isValidNumber()) {
                        const errorCode = iti.getValidationError();
                        let msg = '手机号格式不正确';
                        
                        // 映射错误信息
                        if (typeof intlTelInputUtils !== 'undefined') {
                            if (errorCode === intlTelInputUtils.validationError.TOO_SHORT) {
                                msg = '手机号长度不足';
                            }
                        }
                        
                        // 尝试从 i18n 获取翻译
                        if (window.UDAKEI18N) {
                            const lang = window.UDAKEI18N.getCurrentLanguage();
                            const dictionary = lang === 'zh-CN' ? 'zh-CN' : 'en-US';
                            // 这里简单模拟 getByPath 逻辑或直接硬编码映射，
                            // 鉴于 i18n.js 逻辑，我们直接根据当前语言判断
                            if (errorCode === 1) { // TOO_SHORT
                                msg = lang === 'zh-CN' ? '手机号长度不足' : 'Phone number too short';
                            } else {
                                msg = lang === 'zh-CN' ? '手机号格式不正确' : 'Invalid phone number';
                            }
                        }
                        
                        group.classList.add('has-error');
                        if (phoneErrorMsg) {
                            phoneErrorMsg.innerText = msg;
                            phoneErrorMsg.style.display = 'block';
                        }
                        isValid = false;
                    }
                }
            }
        });
        
        return isValid;
    }
    
    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function validateUsagePurpose(purpose) {
        // 校验用途说明：不低于15个中文字符 或 不低于50个英文字符 (均不包含标点符号)
        // 移除标点符号
        const cleaned = purpose.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()！？，。：；“”（）《》【】]/g, "");
        const chineseChars = cleaned.match(/[\u4e00-\u9fa5]/g) || [];
        const englishChars = cleaned.match(/[a-zA-Z]/g) || [];
        return chineseChars.length >= 15 || englishChars.length >= 50;
    }

    function validateOrganization(industry, organization) {
        // 校验所属单位：结合选择的"所处行业"校验合法性
        if (!organization || !organization.toString().trim()) return false;
        const org = organization.toString().trim();

        if (industry === '教育') {
            // 教育行业常见单位名包含：学院、大学、所、研究所、系；同时支持常见英文形式
            const zhKeywords = ['学院', '大学', '所', '研究所', '系'];
            const enKeywords = ['university', 'college', 'institute', 'school', 'research'];
            const lower = org.toLowerCase();
            return zhKeywords.some(k => org.includes(k)) || enKeywords.some(k => lower.includes(k));
        } else {
            // 其他行业接受常见公司/机构类型中英文关键词
            const keywords = ['集团', '公司', '局', '中心', '院', '所', 'group', 'company', 'corp', 'inc', 'center', 'institute', 'department'];
            const lower = org.toLowerCase();
            return keywords.some(k => lower.includes(k));
        }
    }
    
    // 显示成功模态框
    function showSuccess(id) {
        hideAllModals();
        document.getElementById('displayTicketId').innerText = id;
        showModal(successModal);
    }
    
    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
