import React from "react";
import { Button, Checkbox, FormControl, FormLabel, Input, Modal, ModalBody, ModalCloseButton, ModalContent, ModalFooter, ModalHeader, ModalOverlay, SimpleGrid, Text } from "@chakra-ui/react";

type T = (fa: string, en: string) => string;
export type ConfirmOpts = { title: string; body?: string; danger?: boolean; confirmLabel?: string };

/** Shared replacement for window.confirm(); the confirm button is red for dangerous actions. */
export function ConfirmModal({ opts, t, onConfirm, onClose }: { opts: ConfirmOpts | null; t: T; onConfirm: () => void; onClose: () => void }) {
  return <Modal isOpen={!!opts} onClose={onClose} isCentered><ModalOverlay /><ModalContent mx={3}><ModalHeader>{opts?.title}</ModalHeader><ModalCloseButton />
    {opts?.body && <ModalBody><Text fontSize="sm" wordBreak="break-word">{opts.body}</Text></ModalBody>}
    <ModalFooter gap={2}><Button h="44px" variant="outline" onClick={onClose}>{t("انصراف", "Cancel")}</Button><Button h="44px" colorScheme={opts?.danger ? "red" : "blue"} onClick={onConfirm}>{opts?.confirmLabel ?? t("تأیید", "Confirm")}</Button></ModalFooter></ModalContent></Modal>;
}

/** const [ask, node] = useConfirm(t); render {node} once, then ask({ title, danger: true }, () => doIt()). */
export function useConfirm(t: T) {
  const [st, setSt] = React.useState<{ opts: ConfirmOpts; ok: () => void } | null>(null);
  const ask = (opts: ConfirmOpts, ok: () => void) => setSt({ opts, ok });
  const node = <ConfirmModal opts={st?.opts ?? null} t={t} onClose={() => setSt(null)} onConfirm={() => { const f = st?.ok; setSt(null); f?.(); }} />;
  return [ask, node] as const;
}

/** Form modal replacing the days/GB prompts of the admin recharge. */
export function RechargeModal({ name, t, onSubmit, onClose }: { name: string | null; t: T; onSubmit: (days: number, gb: number, reset: boolean) => void; onClose: () => void }) {
  const [days, setDays] = React.useState("30"); const [gb, setGb] = React.useState("0"); const [reset, setReset] = React.useState(false);
  React.useEffect(() => { if (name !== null) { setDays("30"); setGb("0"); setReset(false); } }, [name]);
  const d = Number(days), g = Number(gb); const bad = !(d >= 0) || !(g >= 0) || (d === 0 && g === 0);
  return <Modal isOpen={name !== null} onClose={onClose} isCentered><ModalOverlay /><ModalContent mx={3}><ModalHeader>{t("شارژ ادمین", "Recharge admin")} {name}</ModalHeader><ModalCloseButton />
    <ModalBody><SimpleGrid columns={1} spacing={3}>
      <FormControl><FormLabel>{t("روز شارژ", "Days to add")}</FormLabel><Input h="44px" type="number" min={0} value={days} onChange={e => setDays(e.target.value)} /></FormControl>
      <FormControl><FormLabel>{t("حجم شارژ (GB)", "GB to add")}</FormLabel><Input h="44px" type="number" min={0} value={gb} onChange={e => setGb(e.target.value)} /></FormControl>
      <Checkbox isChecked={reset} onChange={e => setReset(e.target.checked)}>{t("مصرف کاربران ریست شود", "Reset users' usage")}</Checkbox>
    </SimpleGrid></ModalBody>
    <ModalFooter gap={2}><Button h="44px" variant="outline" onClick={onClose}>{t("انصراف", "Cancel")}</Button><Button h="44px" colorScheme="blue" isDisabled={bad} onClick={() => onSubmit(d, g, reset)}>{t("شارژ", "Recharge")}</Button></ModalFooter></ModalContent></Modal>;
}
