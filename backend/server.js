require('dotenv').config();
const express = require('express');
const cors = require('cors');
const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Security middleware
app.use(cors({
    origin: process.env.ALLOWED_ORIGINS ? process.env.ALLOWED_ORIGINS.split(',') : '*',
    credentials: true
}));
app.use(express.json({ limit: '1mb' }));
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
});

// Data file paths
const DATA_DIR = path.join(__dirname, 'data');
const KEYS_FILE = path.join(DATA_DIR, 'keys.json');
const USAGE_FILE = path.join(DATA_DIR, 'usage.json');

// Ensure data directory exists
async function ensureDataDir() {
    try {
        await fs.mkdir(DATA_DIR, { recursive: true });
    } catch (err) {
        console.error('Error creating data directory:', err);
    }
}

// Initialize data files
async function initDataFiles() {
    await ensureDataDir();
    
    try {
        await fs.access(KEYS_FILE);
    } catch {
        await fs.writeFile(KEYS_FILE, JSON.stringify({ keys: [] }, null, 2));
    }
    
    try {
        await fs.access(USAGE_FILE);
    } catch {
        await fs.writeFile(USAGE_FILE, JSON.stringify({ usage: {} }, null, 2));
    }
}

// Read keys from file
async function readKeys() {
    try {
        const data = await fs.readFile(KEYS_FILE, 'utf8');
        return JSON.parse(data);
    } catch (err) {
        console.error('Error reading keys:', err);
        return { keys: [] };
    }
}

// Write keys to file
async function writeKeys(data) {
    await fs.writeFile(KEYS_FILE, JSON.stringify(data, null, 2));
}

// Read usage from file
async function readUsage() {
    try {
        const data = await fs.readFile(USAGE_FILE, 'utf8');
        return JSON.parse(data);
    } catch (err) {
        console.error('Error reading usage:', err);
        return { usage: {} };
    }
}

// Write usage to file
async function writeUsage(data) {
    await fs.writeFile(USAGE_FILE, JSON.stringify(data, null, 2));
}

// Generate secure access key
function generateAccessKey() {
    const segments = [];
    for (let i = 0; i < 4; i++) {
        const segment = crypto.randomBytes(4).toString('hex').toUpperCase().substring(0, 4);
        segments.push(segment);
    }
    return segments.join('-');
}

// Hash fingerprint for security
function hashFingerprint(fingerprint) {
    return crypto.createHash('sha256').update(fingerprint).digest('hex');
}

// Validate access key
app.post('/api/validate-key', async (req, res) => {
    try {
        const { key, fingerprint } = req.body;
        
        if (!key || !fingerprint) {
            return res.status(400).json({ valid: false, error: 'Key and fingerprint required' });
        }
        
        const keysData = await readKeys();
        const usageData = await readUsage();
        const hashedFingerprint = hashFingerprint(fingerprint);
        
        const keyIndex = keysData.keys.findIndex(k => k.key === key);
        
        if (keyIndex === -1) {
            return res.status(404).json({ valid: false, error: 'Invalid access key' });
        }
        
        const keyData = keysData.keys[keyIndex];
        
        // Check if key is expired
        if (keyData.expiry && Date.now() > keyData.expiry) {
            return res.status(403).json({ valid: false, error: 'Access key has expired' });
        }
        
        // Check if key is already in use by different fingerprint
        if (keyData.fingerprint && keyData.fingerprint !== hashedFingerprint) {
            // Check if this fingerprint is already using another key
            const existingKeyForFingerprint = keysData.keys.find(k => 
                k.fingerprint === hashedFingerprint && k.key !== key && (!k.expiry || Date.now() <= k.expiry)
            );
            
            if (existingKeyForFingerprint) {
                return res.status(403).json({ valid: false, error: 'This device is already using another access key' });
            }
            
            // Mark key as used by this fingerprint
            keyData.fingerprint = hashedFingerprint;
            keyData.usedAt = Date.now();
            keysData.keys[keyIndex] = keyData;
            await writeKeys(keysData);
        } else if (!keyData.fingerprint) {
            // First use of this key
            keyData.fingerprint = hashedFingerprint;
            keyData.usedAt = Date.now();
            keysData.keys[keyIndex] = keyData;
            await writeKeys(keysData);
        }
        
        // Track usage
        if (!usageData.usage[key]) {
            usageData.usage[key] = {
                createdAt: keyData.createdAt,
                usedBy: [],
                totalUses: 0
            };
        }
        
        const fingerprintRecord = usageData.usage[key].usedBy.find(u => u.fingerprint === hashedFingerprint);
        if (fingerprintRecord) {
            fingerprintRecord.lastUsed = Date.now();
            fingerprintRecord.useCount++;
        } else {
            usageData.usage[key].usedBy.push({
                fingerprint: hashedFingerprint,
                firstUsed: Date.now(),
                lastUsed: Date.now(),
                useCount: 1
            });
        }
        usageData.usage[key].totalUses++;
        await writeUsage(usageData);
        
        res.json({
            valid: true,
            expiry: keyData.expiry,
            expiresIn: keyData.expiry ? Math.round((keyData.expiry - Date.now()) / 1000) : null
        });
    } catch (err) {
        console.error('Validation error:', err);
        res.status(500).json({ valid: false, error: 'Validation failed' });
    }
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: Date.now() });
});

// Initialize and start server
initDataFiles().then(() => {
    app.listen(PORT, () => {
        console.log(`🔒 MeDo Backend running on port ${PORT}`);
        console.log(`📁 Data directory: ${DATA_DIR}`);
    });
}).catch(err => {
    console.error('Failed to initialize:', err);
    process.exit(1);
});
