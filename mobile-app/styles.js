import { StyleSheet } from 'react-native';

export default StyleSheet.create({
  full: { flex: 1, backgroundColor: '#111827' },
  setup: { flex: 1, backgroundColor: '#111827' },
  setupInner: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  logo: { fontSize: 48, marginBottom: 8 },
  title: {
    color: '#f3f4f6', fontSize: 24, fontWeight: '700', marginBottom: 6,
    width: '100%', textAlign: 'center',
  },
  subtitle: {
    color: '#9ca3af', fontSize: 13, textAlign: 'center',
    marginBottom: 24, lineHeight: 18, width: '100%',
  },
  qrBtn: {
    backgroundColor: '#7c3aed', borderRadius: 12,
    paddingVertical: 14, paddingHorizontal: 28, width: '100%',
  },
  qrBtnText: { color: '#fff', fontSize: 15, fontWeight: '600', textAlign: 'center' },
  divider: {
    flexDirection: 'row', alignItems: 'center', width: '100%',
    marginVertical: 20, gap: 10,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#374151' },
  dividerTxt: { color: '#6b7280', fontSize: 12 },
  input: {
    width: '100%', backgroundColor: '#1f2937', borderRadius: 12,
    borderWidth: 1, borderColor: '#374151', color: '#f3f4f6',
    fontSize: 16, paddingVertical: 12, paddingHorizontal: 16, textAlign: 'center',
  },
  connectBtn: {
    marginTop: 12, width: '100%', backgroundColor: '#059669',
    borderRadius: 12, paddingVertical: 14,
  },
  connectBtnText: { color: '#fff', fontSize: 15, fontWeight: '600', textAlign: 'center' },
  retryLink: { marginTop: 20 },
  retryLinkText: { color: '#7c3aed', fontSize: 13 },
  scannerClose: {
    position: 'absolute', bottom: 40, alignSelf: 'center',
    backgroundColor: '#111827dd', borderRadius: 24,
    paddingVertical: 12, paddingHorizontal: 28,
  },
  scannerCloseText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});
