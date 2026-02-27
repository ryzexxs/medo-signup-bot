require('dotenv').config();
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder } = require('discord.js');
const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

// Authorized user IDs (qvfear and specified admins)
const AUTHORIZED_USERS = [
    '1033929243215806594',
    '1326206060020629577'
];

// Data file paths
const DATA_DIR = path.join(__dirname, '..', 'backend', 'data');
const KEYS_FILE = path.join(DATA_DIR, 'keys.json');

// Ensure data directory exists
async function ensureDataDir() {
    try {
        await fs.mkdir(DATA_DIR, { recursive: true });
    } catch (err) {
        console.error('Error creating data directory:', err);
    }
}

// Initialize keys file
async function initKeysFile() {
    await ensureDataDir();
    try {
        await fs.access(KEYS_FILE);
    } catch {
        await fs.writeFile(KEYS_FILE, JSON.stringify({ keys: [] }, null, 2));
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

// Generate secure access key
function generateAccessKey() {
    const segments = [];
    for (let i = 0; i < 4; i++) {
        const segment = crypto.randomBytes(4).toString('hex').toUpperCase().substring(0, 4);
        segments.push(segment);
    }
    return segments.join('-');
}

// Parse duration string (e.g., "2m", "1h", "1d")
function parseDuration(durationStr) {
    const match = durationStr.match(/^(\d+)([mhd])$/);
    if (!match) return null;
    
    const value = parseInt(match[1]);
    const unit = match[2];
    
    switch (unit) {
        case 'm': return value * 60 * 1000; // minutes
        case 'h': return value * 60 * 60 * 1000; // hours
        case 'd': return value * 24 * 60 * 60 * 1000; // days
        default: return null;
    }
}

// Format duration for display
function formatDuration(ms) {
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    if (ms < 3600000) return `${Math.round(ms / 60000)}m`;
    if (ms < 86400000) return `${Math.round(ms / 3600000)}h`;
    return `${Math.round(ms / 86400000)}d`;
}

// Discord client setup
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.MessageContent
    ]
});

// Commands
const commands = [
    new SlashCommandBuilder()
        .setName('generate-key')
        .setDescription('Generate a new access key for MeDo Automation')
        .addStringOption(option =>
            option.setName('duration')
                .setDescription('Key duration (e.g., 2m, 1h, 1d)')
                .setRequired(true)
        )
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to assign the key to (optional)')
                .setRequired(false)
        ),
    new SlashCommandBuilder()
        .setName('list-keys')
        .setDescription('List all active access keys'),
    new SlashCommandBuilder()
        .setName('revoke-key')
        .setDescription('Revoke an access key')
        .addStringOption(option =>
            option.setName('key')
                .setDescription('The access key to revoke')
                .setRequired(true)
        ),
    new SlashCommandBuilder()
        .setName('key-stats')
        .setDescription('Show statistics for a specific key')
        .addStringOption(option =>
            option.setName('key')
                .setDescription('The access key to check')
                .setRequired(true)
        )
];

// Check if user is authorized
function isAuthorized(userId) {
    return AUTHORIZED_USERS.includes(userId);
}

// Ready event
client.once('ready', async () => {
    console.log(`✅ Discord bot logged in as ${client.user.tag}`);
    console.log(`📊 Serving ${client.guilds.cache.size} servers`);
    
    // Register commands
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
    
    try {
        console.log('🔄 Registering slash commands...');
        await rest.put(
            Routes.applicationCommands(client.user.id),
            { body: commands.map(cmd => cmd.toJSON()) }
        );
        console.log('✅ Slash commands registered globally');
    } catch (error) {
        console.error('❌ Error registering commands:', error);
    }
    
    await initKeysFile();
    console.log('📁 Keys file initialized');
});

// Interaction handler
client.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;
    
    // Check authorization for all commands
    if (!isAuthorized(interaction.user.id)) {
        return interaction.reply({
            content: '❌ You are not authorized to use this command.',
            ephemeral: true
        });
    }
    
    const { commandName } = interaction;
    
    try {
        switch (commandName) {
            case 'generate-key':
                await handleGenerateKey(interaction);
                break;
            case 'list-keys':
                await handleListKeys(interaction);
                break;
            case 'revoke-key':
                await handleRevokeKey(interaction);
                break;
            case 'key-stats':
                await handleKeyStats(interaction);
                break;
        }
    } catch (error) {
        console.error(`Error handling ${commandName}:`, error);
        const errorMessage = {
            content: '❌ An error occurred while processing your command.',
            ephemeral: true
        };
        
        if (interaction.replied || interaction.deferred) {
            await interaction.followUp(errorMessage);
        } else {
            await interaction.reply(errorMessage);
        }
    }
});

// Generate key handler
async function handleGenerateKey(interaction) {
    await interaction.deferReply({ ephemeral: true });
    
    const durationStr = interaction.options.getString('duration');
    const assignedUser = interaction.options.getUser('user');
    
    // Parse duration
    const durationMs = parseDuration(durationStr);
    if (!durationMs) {
        return interaction.editReply({
            content: '❌ Invalid duration format. Use: `2m` (minutes), `1h` (hours), or `1d` (days)'
        });
    }
    
    // Generate key
    const key = generateAccessKey();
    const expiry = Date.now() + durationMs;
    
    // Save key
    const keysData = await readKeys();
    keysData.keys.push({
        key,
        createdAt: Date.now(),
        expiry,
        duration: durationMs,
        createdBy: interaction.user.id,
        assignedTo: assignedUser?.id || null,
        fingerprint: null,
        usedAt: null
    });
    await writeKeys(keysData);
    
    // Create embed
    const embed = new EmbedBuilder()
        .setColor(0x10b981)
        .setTitle('✅ Access Key Generated')
        .addFields(
            { name: '🔑 Key', value: `\`${key}\``, inline: false },
            { name: '⏱ Duration', value: formatDuration(durationMs), inline: true },
            { name: '📅 Expires', value: `<t:${Math.round(expiry / 1000)}:R>`, inline: true }
        )
        .setFooter({ text: `Generated by ${interaction.user.tag}` })
        .setTimestamp();
    
    if (assignedUser) {
        embed.addFields({ name: '👤 Assigned To', value: assignedUser.tag, inline: true });
    }
    
    // Send key to assigned user in DM if specified
    if (assignedUser) {
        try {
            await assignedUser.send({
                content: `**You have been granted access to MeDo Automation!**\n\nYour access key:\n\`\`\`${key}\`\`\`\n\nThis key will expire ${formatDuration(durationMs)} from now.`,
                embeds: [embed]
            });
            
            return interaction.editReply({
                content: `✅ Key generated and sent to ${assignedUser.tag} via DM!`,
                embeds: [embed]
            });
        } catch (err) {
            console.error('Failed to send DM:', err);
            return interaction.editReply({
                content: `⚠️ Key generated but couldn't send DM to ${assignedUser.tag} (they may have DMs disabled). Key: \`${key}\``,
                embeds: [embed]
            });
        }
    }
    
    await interaction.editReply({ embeds: [embed] });
}

// List keys handler
async function handleListKeys(interaction) {
    await interaction.deferReply({ ephemeral: true });
    
    const keysData = await readKeys();
    const now = Date.now();
    
    // Filter active keys
    const activeKeys = keysData.keys.filter(k => !k.expiry || k.expiry > now);
    
    if (activeKeys.length === 0) {
        return interaction.editReply({ content: 'No active access keys found.' });
    }
    
    const embed = new EmbedBuilder()
        .setColor(0x5865F2)
        .setTitle('📋 Active Access Keys')
        .setDescription(`Total: ${activeKeys.length} key(s)`);
    
    // Group by status
    const usedKeys = activeKeys.filter(k => k.fingerprint);
    const unusedKeys = activeKeys.filter(k => !k.fingerprint);
    
    if (usedKeys.length > 0) {
        embed.addFields({
            name: `🟢 In Use (${usedKeys.length})`,
            value: usedKeys.slice(0, 5).map(k => 
                `\`${k.key}\` - Expires <t:${Math.round(k.expiry / 1000)}:R>`
            ).join('\n') + (usedKeys.length > 5 ? `\n*...and ${usedKeys.length - 5} more*` : ''),
            inline: false
        });
    }
    
    if (unusedKeys.length > 0) {
        embed.addFields({
            name: `🔵 Unused (${unusedKeys.length})`,
            value: unusedKeys.slice(0, 5).map(k => 
                `\`${k.key}\` - Expires <t:${Math.round(k.expiry / 1000)}:R>`
            ).join('\n') + (unusedKeys.length > 5 ? `\n*...and ${unusedKeys.length - 5} more*` : ''),
            inline: false
        });
    }
    
    embed.setFooter({ text: `Requested by ${interaction.user.tag}` })
        .setTimestamp();
    
    await interaction.editReply({ embeds: [embed] });
}

// Revoke key handler
async function handleRevokeKey(interaction) {
    await interaction.deferReply({ ephemeral: true });
    
    const keyToRevoke = interaction.options.getString('key');
    const keysData = await readKeys();
    
    const keyIndex = keysData.keys.findIndex(k => k.key === keyToRevoke);
    
    if (keyIndex === -1) {
        return interaction.editReply({ content: '❌ Access key not found.' });
    }
    
    const revokedKey = keysData.keys[keyIndex];
    keysData.keys.splice(keyIndex, 1);
    await writeKeys(keysData);
    
    const embed = new EmbedBuilder()
        .setColor(0xef4444)
        .setTitle('🚫 Key Revoked')
        .addFields(
            { name: '🔑 Key', value: `\`${keyToRevoke}\``, inline: false },
            { name: '📅 Was Expiring', value: `<t:${Math.round(revokedKey.expiry / 1000)}:R>`, inline: true },
            { name: '👁️ Used', value: revokedKey.fingerprint ? 'Yes' : 'No', inline: true }
        )
        .setFooter({ text: `Revoked by ${interaction.user.tag}` })
        .setTimestamp();
    
    await interaction.editReply({ embeds: [embed] });
}

// Key stats handler
async function handleKeyStats(interaction) {
    await interaction.deferReply({ ephemeral: true });
    
    const keyToCheck = interaction.options.getString('key');
    const keysData = await readKeys();
    
    const keyData = keysData.keys.find(k => k.key === keyToCheck);
    
    if (!keyData) {
        return interaction.editReply({ content: '❌ Access key not found.' });
    }
    
    const now = Date.now();
    const isExpired = keyData.expiry && keyData.expiry < now;
    
    const embed = new EmbedBuilder()
        .setColor(isExpired ? 0xef4444 : (keyData.fingerprint ? 0x10b981 : 0xf59e0b))
        .setTitle('📊 Key Statistics')
        .addFields(
            { name: '🔑 Key', value: `\`${keyData.key}\``, inline: false },
            { name: '📅 Created', value: `<t:${Math.round(keyData.createdAt / 1000)}:R>`, inline: true },
            { name: '⏱ Duration', value: formatDuration(keyData.duration), inline: true },
            { name: '📅 Expires', value: keyData.expiry ? `<t:${Math.round(keyData.expiry / 1000)}:R>` : 'Never', inline: true },
            { name: '👁️ Status', value: isExpired ? '⚰️ Expired' : (keyData.fingerprint ? '🟢 In Use' : '🔵 Unused'), inline: true },
            { name: '👤 Assigned To', value: keyData.assignedTo ? `<@${keyData.assignedTo}>` : 'Not assigned', inline: true }
        )
        .setFooter({ text: `Requested by ${interaction.user.tag}` })
        .setTimestamp();
    
    if (keyData.usedAt) {
        embed.addFields({
            name: '🕐 First Used',
            value: `<t:${Math.round(keyData.usedAt / 1000)}:R>`,
            inline: true
        });
    }
    
    await interaction.editReply({ embeds: [embed] });
}

// Login
client.login(process.env.DISCORD_TOKEN);
