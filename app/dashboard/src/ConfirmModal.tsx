import React from "react";
import { Button, Checkbox, FormControl, FormLabel, HStack, Input, Modal, ModalBody, ModalCloseButton, ModalContent, ModalHeader, ModalOverlay, SimpleGrid, Text } from "@chakra-ui/react";

type T = (fa: string, en: string) => string;
export type Ask = { title: string; text?: string; danger?: boolean; okLabel?: string; onOk: () => void };

/** Replacement for window.confirm(): red confirm button for dangerous actions. */
export function ConfirmModal({ ask, onClose, t }: { ask: Ask | null; onClose: () => void; t: T }) {
  return <Modal isOpen={!!ask} onClose={onClose} isCentered><ModalOverlay /><ModalContent mx={3}><ModalHeader>{ask?.title}</ModalHeader><ModalCloseButton /><ModalBody pb={5}>
    {ask?.text && <Text fontSize="sm" mb={4}>{ask.text}</Text>}
    <HStack><Button h="44px" colorScheme={ask?.danger ? "red" : "blue"} onClick={() => { const f = ask?.onOk; onClose(); f?.(); }}>{ask?.okLabel || t("تأیید", "Confirm")}</Button><Button h="44px" variant="outline" onClick={onClose}>{t("انصراف", "Cancel")}</Button></HStack>
  </ModalBody></ModalContent></Modal>;
}

/** `const [confirm, node] = useConfirm(t)`: render `{node}` once, call confirm({...}) anywhere. */
export function useConfirm(t: T): [(a: Ask) => void, React.ReactNode] {
  const [ask, setAsk] = React.useState<Ask | null>(null);
  return [setAsk, <ConfirmModal key="confirm-modal" ask={ask} onClose={() => setAsk(null)} t={t} />];
}

/** Replacement for the days/GB prompt() pair when recharging an admin. */
export function RechargeModal({ target, onClose, onSubmit, t }: { target: string | null; onClose: () => void; onSubmit: (days: number, gb: number, reset: boolean) => void; t: T }) {
  const [d, setD] = React.useState("30"); const [g, setG] = React.useState("0"); const [r, setR] = React.useState(false);
  React.useEffect(() => { if (target) { setD("30"); setG("0"); setR(false); } }, [target]);
  const days = Math.floor(Number(d)), gb = Number(g);
  const ok = Number.isFinite(days) && days >= 0 && Number.isFinite(gb) && gb >= 0 && (days > 0 || gb > 0 || r);
  return <Modal isOpen={!!target} onClose={onClose} isCentered><ModalOverlay /><ModalContent mx={3}><ModalHeader>{t("شارژ ادمین", "Recharge admin")} {target}</ModalHeader><ModalCloseButton /><ModalBody pb={5}>
    <SimpleGrid columns={2} spacing={3}>
      <FormControl><FormLabel>{t("روز", "Days")}</FormLabel><Input type="number" min={0} inputMode="numeric" value={d} onChange={e => setD(e.target.value)} /></FormControl>
      <FormControl><FormLabel>{t("حجم (GB)", "Traffic (GB)")}</FormLabel><Input type="number" min={0} inputMode="decimal" value={g} onChange={e => setG(e.target.value)} /></FormControl>
    </SimpleGrid>
    <Checkbox mt={3} isChecked={r} onChange={e => setR(e.target.checked)}>{t("مصرف کاربران ریست شود", "Reset users' usage")}</Checkbox>
    <HStack mt={4}><Button h="44px" colorScheme="blue" isDisabled={!ok} onClick={() => { onSubmit(days, gb, r); onClose(); }}>{t("شارژ", "Recharge")}</Button><Button h="44px" variant="outline" onClick={onClose}>{t("انصراف", "Cancel")}</Button></HStack>
  </ModalBody></ModalContent></Modal>;
}
