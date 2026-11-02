import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Label } from '@/components/ui/label.js';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select.js';
import type { LocaleMessages } from '@/i18n/en.js';

type EditorCopy = LocaleMessages['ontology']['hub']['editor'];

type ClassOption = { id: string; label: string };

type OntologyEditorPropertyDialogProps = {
  copy: EditorCopy;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classOptions: ClassOption[];
  domainUri: string;
  rangeUri: string;
  onDomainChange: (uri: string) => void;
  onRangeChange: (uri: string) => void;
  onConfirm: () => void;
  cancelLabel: string;
};

export function OntologyEditorPropertyDialog({
  copy,
  open,
  onOpenChange,
  classOptions,
  domainUri,
  rangeUri,
  onDomainChange,
  onRangeChange,
  onConfirm,
  cancelLabel,
}: OntologyEditorPropertyDialogProps) {
  const canConfirm = Boolean(domainUri && rangeUri && domainUri !== rangeUri);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{copy.add_property_dialog_title}</DialogTitle>
          <DialogDescription>{copy.add_property_dialog_desc}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label>{copy.label_property_domain}</Label>
            <NativeSelect
              value={domainUri}
              onChange={(event) => onDomainChange(event.target.value)}
              className="text-xs"
              size="sm"
            >
              <NativeSelectOption value="">{copy.pick_class}</NativeSelectOption>
              {classOptions.map((option) => (
                <NativeSelectOption key={option.id} value={option.id}>
                  {option.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="grid gap-2">
            <Label>{copy.label_property_range}</Label>
            <NativeSelect
              value={rangeUri}
              onChange={(event) => onRangeChange(event.target.value)}
              className="text-xs"
              size="sm"
            >
              <NativeSelectOption value="">{copy.pick_class}</NativeSelectOption>
              {classOptions.map((option) => (
                <NativeSelectOption key={option.id} value={option.id}>
                  {option.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button type="button" disabled={!canConfirm} onClick={onConfirm}>
            {copy.add_property_confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
