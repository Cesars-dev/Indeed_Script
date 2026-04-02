"""
DOM Scanner — extracts all form elements from the current page.
Runs via page.evaluate() in <100ms, zero API calls.
"""


async def scan_dom(page) -> dict:
    """Extract all interactive form elements from the current page."""
    return await page.evaluate("""() => {
        const result = {
            url: window.location.href,
            buttons: [],
            radios: [],
            inputs: [],
            selects: [],
            checkboxes: [],
            file_inputs: 0,
            success: false,
            disqualified: false,
            errors: []
        };

        // ── Buttons ──
        result.buttons = [...document.querySelectorAll('button, [role="button"], a[class*="btn"]')]
            .filter(b => b.offsetParent !== null)
            .map(b => ({
                text: b.textContent.trim().substring(0, 80),
                type: b.type || '',
                disabled: b.disabled || b.getAttribute('aria-disabled') === 'true'
            }));

        // ── Radio groups ──
        const radioInputs = document.querySelectorAll('input[type="radio"]');
        const processedNames = new Set();
        radioInputs.forEach(r => {
            if (processedNames.has(r.name)) return;
            processedNames.add(r.name);

            const container = r.closest('fieldset')
                || r.closest('[role="radiogroup"]')
                || r.closest('[data-testid]')
                || r.parentElement?.parentElement?.parentElement;

            let question = '';
            if (container) {
                const legend = container.querySelector('legend, [id*="label"], [class*="label"]');
                question = legend?.textContent?.trim() || '';
                if (!question) {
                    for (const el of container.querySelectorAll('span, p, div, label')) {
                        const t = el.textContent?.trim();
                        if (t && t.length > 5 && !['Yes', 'No', 'yes', 'no'].includes(t)) {
                            question = t.substring(0, 150);
                            break;
                        }
                    }
                }
            }
            // Fallback: climb UP the DOM tree to find question text (Indeed puts labels as siblings)
            if (!question) {
                let node = r.parentElement;
                for (let depth = 0; depth < 6 && node; depth++) {
                    const lbl = node.querySelector('[class*="label"], [class*="question"], [id*="label"], [id*="question"], legend');
                    if (lbl) {
                        const t = lbl.textContent?.trim();
                        if (t && t.length > 5 && !['Yes', 'No', 'yes', 'no'].includes(t)) {
                            question = t.substring(0, 150);
                            break;
                        }
                    }
                    node = node.parentElement;
                }
            }

            const siblings = document.querySelectorAll('input[name="' + r.name + '"]');
            const options = [...siblings].map(s => ({
                text: (s.labels?.[0] || s.nextElementSibling)?.textContent?.trim() || '',
                value: s.value,
                selected: s.checked
            }));

            result.radios.push({ question, options, name: r.name });
        });

        // ── Text inputs ──
        result.inputs = [...document.querySelectorAll(
            'input[type="text"], input[type="number"], input[type="tel"], input[type="email"], textarea'
        )]
            .filter(i => i.offsetParent !== null && !i.readOnly)
            .map(i => ({
                label: (document.querySelector('label[for="' + i.id + '"]')?.textContent?.trim()
                    || i.getAttribute('aria-label')
                    || i.placeholder || '').substring(0, 120),
                value: i.value,
                required: i.required || i.getAttribute('aria-required') === 'true',
                type: i.type,
                id: i.id || ''
            }));

        // ── Selects ──
        result.selects = [...document.querySelectorAll('select')]
            .filter(s => s.offsetParent !== null)
            .map(s => ({
                label: (document.querySelector('label[for="' + s.id + '"]')?.textContent?.trim() || '').substring(0, 120),
                id: s.id || '',
                value: s.value,
                options: [...s.options].map(o => ({ text: o.text, value: o.value, selected: o.selected }))
            }));

        // ── Checkboxes ──
        result.checkboxes = [...document.querySelectorAll('input[type="checkbox"]')]
            .filter(c => c.offsetParent !== null)
            .map(c => ({
                label: (c.labels?.[0])?.textContent?.trim()?.substring(0, 120) || '',
                checked: c.checked,
                id: c.id || ''
            }));

        // ── File inputs ──
        // NOTE: Do NOT filter by offsetParent — Indeed hides file inputs behind
        // styled buttons. Playwright's set_input_files() works on hidden elements.
        result.file_inputs = document.querySelectorAll('input[type="file"]').length;

        // ── Modals / overlays ──
        result.modals = [...document.querySelectorAll('[role="dialog"], [aria-modal="true"]')]
            .filter(m => m.offsetParent !== null)
            .map(m => ({
                text: m.textContent.trim().substring(0, 200),
                hasCloseButton: m.querySelector('[aria-label="Close"], [aria-label="close"], button[class*="Close"]') !== null
            }));

        // ── reCAPTCHA ──
        result.has_recaptcha = document.querySelector('iframe[src*="google.com/recaptcha"]') !== null
            || document.querySelector('.g-recaptcha') !== null
            || document.querySelector('[data-sitekey]') !== null;

        // ── Success / disqualification signals ──
        const bodyText = document.body.textContent || '';
        result.success = bodyText.includes('Application submitted')
            || bodyText.includes('application was submitted')
            || bodyText.includes('You applied')
            || bodyText.includes('Thank you for your application')
            || bodyText.includes('Your application has been received')
            || bodyText.includes('Application Complete')
            || bodyText.includes('Thank you for applying')
            || bodyText.includes('Successfully submitted');

        result.disqualified = bodyText.includes('may not hear back')
            || bodyText.includes('Consider additional opportunities');

        // ── Error messages ──
        result.errors = [...document.querySelectorAll('[class*="error" i], [role="alert"], [class*="Error"]')]
            .filter(e => e.offsetParent !== null)
            .map(e => e.textContent.trim().substring(0, 120))
            .filter(t => t.length > 0);

        return result;
    }""")
