import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ActivityIndicator,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { CameraView, useCameraPermissions } from 'expo-camera';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';
import { discoverServer, verifyServer } from './discovery';
import styles from './styles';

const STORAGE_KEY = 'remote-control:last-ip';
const SETTINGS_KEY = 'remote-control:settings';
const MAX_WEBVIEW_FAILURES = 3;
const RETRY_BACKOFF_MS = 1500;

export default function App() {
  const [phase, setPhase] = useState('checking'); // checking | discovering | setup | connected
  const [ip, setIp] = useState(null);
  const [inputIp, setInputIp] = useState('');
  const [scannerOpen, setScannerOpen] = useState(false);
  const [statusText, setStatusText] = useState('Procurando servidor salvo...');
  const [permission, requestPermission] = useCameraPermissions();

  const failuresRef = useRef(0);
  const webviewRef = useRef(null);
  // Configurações (sensibilidade etc.) ficam salvas no celular, não na página —
  // o IP do PC muda a cada conexão (DHCP), e localStorage é isolado por origem.
  const settingsRef = useRef(null);

  const goToSetup = useCallback((message) => {
    failuresRef.current = 0;
    setStatusText(message || 'Escaneie o QR Code ou digite o IP do servidor');
    setPhase('setup');
  }, []);

  const connectTo = useCallback(async (candidateIp) => {
    await AsyncStorage.setItem(STORAGE_KEY, candidateIp);
    failuresRef.current = 0;
    setIp(candidateIp);
    setPhase('connected');
  }, []);

  const runDiscovery = useCallback(async () => {
    setPhase('discovering');
    setStatusText('Procurando servidor na rede...');
    const found = await discoverServer();
    if (found) {
      await connectTo(found);
    } else {
      goToSetup('Servidor não encontrado na rede. Escaneie o QR Code ou digite o IP.');
    }
  }, [connectTo, goToSetup]);

  useEffect(() => {
    (async () => {
      settingsRef.current = await AsyncStorage.getItem(SETTINGS_KEY);
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      if (!saved) {
        runDiscovery();
        return;
      }
      setStatusText('Reconectando ao último servidor...');
      const ok = await verifyServer(saved);
      if (ok) {
        connectTo(saved);
      } else {
        await AsyncStorage.removeItem(STORAGE_KEY);
        runDiscovery();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sem isso, uma falha de rede fazia o WebView recarregar pra sempre no mesmo IP morto.
  const handleWebViewFailure = useCallback(() => {
    failuresRef.current += 1;
    if (failuresRef.current >= MAX_WEBVIEW_FAILURES) {
      AsyncStorage.removeItem(STORAGE_KEY);
      goToSetup('Conexão perdida com o servidor.');
      return;
    }
    setTimeout(() => {
      webviewRef.current?.reload();
    }, RETRY_BACKOFF_MS);
  }, [goToSetup]);

  // Ação explícita do usuário (botão "Trocar servidor" na página web) — diferente de
  // uma falha de conexão, não deve tentar reconectar no mesmo IP nem re-buscar sozinho.
  const handleChangeServer = useCallback(() => {
    AsyncStorage.removeItem(STORAGE_KEY);
    goToSetup('Escolha um novo servidor.');
  }, [goToSetup]);

  const handleManualConnect = useCallback(async () => {
    const candidate = inputIp.trim();
    if (!candidate) return;
    setStatusText('Conectando...');
    setPhase('checking');
    const ok = await verifyServer(candidate, 4000);
    if (ok) {
      connectTo(candidate);
    } else {
      goToSetup('Não foi possível conectar nesse IP. Verifique e tente novamente.');
    }
  }, [inputIp, connectTo, goToSetup]);

  const handleBarcodeScanned = useCallback(async ({ data }) => {
    setScannerOpen(false);
    try {
      const url = new URL(data);
      const candidate = url.hostname;
      setStatusText('Conectando...');
      setPhase('checking');
      const ok = await verifyServer(candidate, 4000);
      if (ok) {
        connectTo(candidate);
      } else {
        goToSetup('QR Code inválido ou servidor indisponível.');
      }
    } catch {
      goToSetup('QR Code inválido.');
    }
  }, [connectTo, goToSetup]);

  const openScanner = useCallback(async () => {
    if (!permission?.granted) {
      const res = await requestPermission();
      if (!res.granted) return;
    }
    setScannerOpen(true);
  }, [permission, requestPermission]);

  if (scannerOpen) {
    return (
      <View style={styles.full}>
        <StatusBar hidden />
        <CameraView
          style={styles.full}
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          onBarcodeScanned={handleBarcodeScanned}
        />
        <TouchableOpacity style={styles.scannerClose} onPress={() => setScannerOpen(false)}>
          <Text style={styles.scannerCloseText}>Cancelar</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (phase === 'connected' && ip) {
    return (
      <View style={styles.full}>
        <StatusBar hidden />
        <WebView
          ref={webviewRef}
          style={styles.full}
          source={{ uri: `http://${ip}:5000` }}
          onError={handleWebViewFailure}
          onHttpError={handleWebViewFailure}
          injectedJavaScriptBeforeContentLoaded={
            settingsRef.current
              ? `(function(){try{var s=${settingsRef.current};
                  if(s.cursorSens!=null)localStorage.setItem('rc_cursor_sens',s.cursorSens);
                  if(s.scrollAmt!=null)localStorage.setItem('rc_scroll_amt',s.scrollAmt);
                  if(s.singleTapClick!=null)localStorage.setItem('rc_single_tap_click',String(s.singleTapClick));
                }catch(e){}})();true;`
              : undefined
          }
          onMessage={(e) => {
            const data = e.nativeEvent.data;
            if (data === 'reconnect') {
              handleChangeServer();
              return;
            }
            try {
              const msg = JSON.parse(data);
              if (msg && msg.type === 'settings') {
                const { type, ...settings } = msg;
                const json = JSON.stringify(settings);
                settingsRef.current = json;
                AsyncStorage.setItem(SETTINGS_KEY, json);
              }
            } catch {
              // mensagem desconhecida, ignora
            }
          }}
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          overScrollMode="never"
          bounces={false}
        />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.setup}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <StatusBar hidden />
      <View style={styles.setupInner}>
        <Text style={styles.logo}>📡</Text>
        <Text style={styles.title}>Remote Control</Text>
        <Text style={styles.subtitle}>{statusText}</Text>

        {(phase === 'checking' || phase === 'discovering') && (
          <ActivityIndicator color="#7c3aed" size="large" style={{ marginVertical: 16 }} />
        )}

        {phase === 'setup' && (
          <>
            <TouchableOpacity style={styles.qrBtn} onPress={openScanner} activeOpacity={0.8}>
              <Text style={styles.qrBtnText}>📷  Escanear QR Code</Text>
            </TouchableOpacity>

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerTxt}>ou</Text>
              <View style={styles.dividerLine} />
            </View>

            <TextInput
              style={styles.input}
              value={inputIp}
              onChangeText={setInputIp}
              placeholder="192.168.0.100"
              placeholderTextColor="#4b5563"
              keyboardType="numeric"
            />
            <TouchableOpacity style={styles.connectBtn} onPress={handleManualConnect} activeOpacity={0.8}>
              <Text style={styles.connectBtnText}>Conectar</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.retryLink} onPress={runDiscovery}>
              <Text style={styles.retryLinkText}>🔄  Buscar na rede novamente</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}
